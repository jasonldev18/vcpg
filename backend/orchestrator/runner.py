"""Drives one step: teach → build → review → tour → gate (SPEC section 5).

Building lives in build.py. Until slides exist (phase 4), a passed gate marks the slide done
without writing one.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

from backend import db
from backend.errors import Conflict, NotFound
from backend.events import bus
from backend.gate import rubric
from backend.gate.rubric import Item
from backend.llm import client
from backend.orchestrator.context import history, tag, user_message
from backend.orchestrator.machine import State, transition
from backend.schemas import BuildNote, GateGrade, ReviewNote, Tour
from backend.workspace import git

S = State


# ---- reading state


def _step(conn: sqlite3.Connection, step_id: int) -> sqlite3.Row:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM steps WHERE id = ?", (step_id,)
    ).fetchone()
    if row is None:
        raise NotFound(f"Step {step_id} does not exist.")
    return row


def current_step_id(conn: sqlite3.Connection, project_id: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM steps WHERE project_id = ? AND state != 'slide_done'"
        " ORDER BY position LIMIT 1",
        (project_id,),
    ).fetchone()
    return row["id"] if row else None


def _current(conn: sqlite3.Connection, step_id: int, *states: State) -> sqlite3.Row:
    step = _step(conn, step_id)
    if current_step_id(conn, step["project_id"]) != step_id:
        raise Conflict("This step is locked until the earlier steps pass their gates.")
    if states and step["state"] not in states:
        raise Conflict(f"This step is {step['state']}; that action needs {'/'.join(states)}.")
    return step


def _items(conn: sqlite3.Connection, step_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM rubric_items WHERE step_id = ? ORDER BY id", (step_id,)
    ).fetchall()


def _messages(conn: sqlite3.Connection, step_id: int, where: str) -> list[sqlite3.Row]:
    return conn.execute(
        f"SELECT id, agent, role, content FROM messages WHERE step_id = ? AND ({where})"
        " ORDER BY id",
        (step_id,),
    ).fetchall()


GATE = "agent = 'interviewer' OR (agent = 'tutor' AND role = 'reteach')"
CHAT = "agent = 'tutor' AND role IN ('user', 'assistant')"


def _answers(conn: sqlite3.Connection, step_id: int) -> list[str]:
    return [
        m["content"] for m in _messages(conn, step_id, "agent = 'interviewer' AND role = 'user'")
    ]


def _attempts(conn: sqlite3.Connection, step_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT kind, grader_json FROM attempts WHERE step_id = ? ORDER BY id", (step_id,)
    ).fetchall()


# ---- writing state


def _set_state(conn: sqlite3.Connection, step: sqlite3.Row, target: State) -> None:
    transition(State(step["state"]), target)
    conn.execute("UPDATE steps SET state = ? WHERE id = ?", (target, step["id"]))
    bus.publish(step["project_id"], "state_changed", step_id=step["id"], state=target)


def _say(conn: sqlite3.Connection, step: sqlite3.Row, agent: str, role: str, text: str) -> None:
    conn.execute(
        "INSERT INTO messages (project_id, step_id, agent, role, content) VALUES (?, ?, ?, ?, ?)",
        (step["project_id"], step["id"], agent, role, text),
    )


def _advance(step_id: int, *path: State) -> None:
    with db.session() as conn:
        for target in path:
            _set_state(conn, _step(conn, step_id), target)


# ---- context for agents


def _step_block(step: sqlite3.Row) -> str:
    return tag(
        "step",
        f"Title: {step['title']}\nComponent: {step['component']}\nGoal: {step['goal']}\n"
        f"Concepts: {', '.join(json.loads(step['concepts']))}\n"
        f"Files: {', '.join(json.loads(step['files']))}\n"
        f"Acceptance:\n" + "\n".join(f"- {a}" for a in json.loads(step["acceptance"])),
    )


def _plan_block(conn: sqlite3.Connection, project_id: int) -> str:
    project = conn.execute(
        "SELECT name, brief FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    titles = conn.execute(
        "SELECT position, title FROM steps WHERE project_id = ? ORDER BY position", (project_id,)
    ).fetchall()
    steps = "\n".join(f"{r['position'] + 1}. {r['title']}" for r in titles)
    return tag("plan", f"Project: {project['name']}\nBrief: {project['brief']}\nSteps:\n{steps}")


def _lesson(conn: sqlite3.Connection, step_id: int) -> str | None:
    rows = _messages(conn, step_id, "agent = 'tutor' AND role = 'lesson'")
    return rows[-1]["content"] if rows else None


def build_summary(step: sqlite3.Row) -> str:
    """What the code does, for the tutor, interviewer and grader: the notes and tour stops."""
    lines: list[str] = []
    if step["build_note"]:
        note = BuildNote.model_validate_json(step["build_note"])
        lines += [f"{f.path}: {f.summary}" for f in note.files]
        lines += [f"Decision: {d}" for d in note.decisions]
    if step["review_note"]:
        review = ReviewNote.model_validate_json(step["review_note"])
        lines += [f"Reviewer cut from {c.path}: {c.what} ({c.why})" for c in review.cut]
        lines += [f"Reviewer fixed in {f.path}: {f.what}" for f in review.fixed]
    if step["tour_json"]:
        tour = Tour.model_validate_json(step["tour_json"])
        lines += [f"Code at {s.file}:{s.line_start}-{s.line_end}" for s in tour.stops]
    return "\n".join(lines)


def _repo(conn: sqlite3.Connection, project_id: int) -> Path:
    row = conn.execute("SELECT workspace_path FROM projects WHERE id = ?", (project_id,)).fetchone()
    return Path(row["workspace_path"])


COMMIT_LIMIT = 80_000


def _commit(conn: sqlite3.Connection, step: sqlite3.Row) -> str:
    shown = git.show(_repo(conn, step["project_id"]), step["commit_sha"])
    return shown[:COMMIT_LIMIT] + ("\n[diff truncated]" if len(shown) > COMMIT_LIMIT else "")


def _transcript(rows: list[sqlite3.Row]) -> str:
    speaker = {"user": "Learner", "assistant": "Interviewer", "reteach": "Tutor (re-teach)"}
    return "\n\n".join(f"{speaker[r['role']]}: {r['content']}" for r in rows) or "(not started)"


def _rubric_block(items: list[sqlite3.Row]) -> str:
    return tag(
        "rubric", "\n".join(f"{i}. {r['text']} [{r['status']}]" for i, r in enumerate(items))
    )


def _last_gap(conn: sqlite3.Connection, step_id: int) -> str:
    graded = [a for a in _attempts(conn, step_id) if a["kind"] == "answer"]
    return json.loads(graded[-1]["grader_json"])["grade"]["gap"] if graded else "none yet"


# ---- teach and chat


async def teach(step_id: int) -> None:
    with db.session() as conn:
        step = _current(conn, step_id, S.PLANNED)
        if _lesson(conn, step_id) is not None:
            return
        msg = user_message(
            tag("mode", "teach"),
            _plan_block(conn, step["project_id"]),
            _step_block(step),
            tag("history", history(conn, step["project_id"])),
        )
    lesson = await client.text(
        "tutor", msg, project_id=step["project_id"], step_id=step_id, stream=True
    )
    with db.session() as conn:
        _say(conn, step, "tutor", "lesson", lesson)


async def ask(step_id: int, question: str) -> None:
    with db.session() as conn:
        step = _current(conn, step_id)
        chat = _messages(conn, step_id, CHAT)
        msg = user_message(
            tag("mode", "chat"),
            _plan_block(conn, step["project_id"]),
            _step_block(step),
            tag("lesson", _lesson(conn, step_id) or "(not written yet)"),
            tag("build_summary", build_summary(step) or "(no code yet)"),
            *([tag("commit", _commit(conn, step))] if step["commit_sha"] else []),
            tag("conversation", "\n\n".join(f"{m['role']}: {m['content']}" for m in chat)),
            tag("question", question),
        )
        _say(conn, step, "tutor", "user", question)
    reply = await client.text(
        "tutor", msg, project_id=step["project_id"], step_id=step_id, stream=True
    )
    with db.session() as conn:
        _say(conn, step, "tutor", "assistant", reply)


# ---- code tour


async def tour(step_id: int) -> None:
    with db.session() as conn:
        step = _current(conn, step_id, S.REVIEWED)
        if step["tour_json"]:
            return
        msg = user_message(
            tag("mode", "tour"),
            _plan_block(conn, step["project_id"]),
            _step_block(step),
            tag("commit", _commit(conn, step)),
            tag("build_note", step["build_note"] or ""),
            tag("review_note", step["review_note"] or ""),
        )
    stops = await client.structured(
        "tutor", msg, Tour, project_id=step["project_id"], step_id=step_id
    )
    with db.session() as conn:
        conn.execute(
            "UPDATE steps SET tour_json = ? WHERE id = ?", (stops.model_dump_json(), step_id)
        )


def file_at_commit(step_id: int, path: str) -> list[str]:
    """A file from the step's commit, for the tour. Only files the tour stops at."""
    with db.session() as conn:
        step = _step(conn, step_id)
        if not step["tour_json"] or path not in {
            s.file for s in Tour.model_validate_json(step["tour_json"]).stops
        }:
            raise NotFound(f"{path} is not part of this step's tour.")
        repo = _repo(conn, step["project_id"])
    return git.file_at(repo, step["commit_sha"], path).splitlines()


# ---- gate


async def _interviewer(step_id: int, request: str) -> None:
    with db.session() as conn:
        step = _step(conn, step_id)
        msg = user_message(
            _step_block(step),
            tag("build_summary", build_summary(step)),
            _rubric_block(_items(conn, step_id)),
            tag("gap", _last_gap(conn, step_id)),
            tag("conversation", _transcript(_messages(conn, step_id, GATE))),
            tag("request", request),
        )
    question = await client.text(
        "interviewer", msg, project_id=step["project_id"], step_id=step_id, stream=True
    )
    with db.session() as conn:
        _say(conn, step, "interviewer", "assistant", question)


async def start_interview(step_id: int) -> None:
    with db.session() as conn:  # TOURED too, so a failed first question can be retried
        if _current(conn, step_id, S.REVIEWED, S.TOURED)["state"] == S.REVIEWED:
            _set_state(conn, _step(conn, step_id), S.TOURED)
    await _interviewer(step_id, "question")
    _advance(step_id, S.INTERVIEWING)


def grader_message(
    rubric_items: list[str], step: str, build_summary: str, answers: list[str], questions: list[str]
) -> list[dict[str, str]]:
    """Shared by the gate and the calibration suite, so both grade the same way."""
    return user_message(
        tag("rubric", "\n".join(f"{i}. {text}" for i, text in enumerate(rubric_items))),
        step,
        tag("build_summary", build_summary),
        tag("learner_answers", "\n\n".join(f"[{i + 1}] {a}" for i, a in enumerate(answers))),
        tag("interviewer_questions", "\n\n".join(questions)),
    )


async def _grade(step_id: int, project_id: int) -> GateGrade:
    with db.session() as conn:
        step = _step(conn, step_id)
        gate = _messages(conn, step_id, GATE)
        msg = grader_message(
            [r["text"] for r in _items(conn, step_id)],
            _step_block(step),
            build_summary(step),
            [m["content"] for m in gate if m["role"] == "user"],
            [m["content"] for m in gate if m["role"] == "assistant"],
        )
    return await client.structured("grader", msg, GateGrade, project_id=project_id, step_id=step_id)


async def answer(step_id: int, text: str) -> None:
    with db.session() as conn:
        step = _current(conn, step_id, S.INTERVIEWING)
        _say(conn, step, "interviewer", "user", text)
    grade = await _grade(step_id, step["project_id"])

    with db.session() as conn:
        rows = _items(conn, step_id)
        before = [Item(r["text"], r["status"], r["evidence"]) for r in rows]
        after = rubric.merge(before, grade, _answers(conn, step_id))
        for row, item in zip(rows, after, strict=True):
            conn.execute(
                "UPDATE rubric_items SET status = ?, evidence = ? WHERE id = ?",
                (item.status, item.evidence, row["id"]),
            )
        improved = rubric.improved(before, after)
        conn.execute(
            "INSERT INTO attempts (step_id, kind, content, grader_json) VALUES (?, 'answer', ?, ?)",
            (step_id, text, json.dumps({"grade": grade.model_dump(), "improved": improved})),
        )
        bus.publish(step["project_id"], "gate_update", step_id=step_id, **rubric.progress(after))
        since_reteach = _since_last(_attempts(conn, step_id), "reteach")
        stuck = rubric.needs_reteach(
            [
                json.loads(a["grader_json"])["improved"]
                for a in since_reteach
                if a["kind"] == "answer"
            ]
        )

    if rubric.passed(after):
        _advance(step_id, S.PASSED, S.SLIDE_DONE)  # slides arrive in phase 4
    elif stuck:
        await reteach(step_id)
    else:
        _advance(step_id, S.INTERVIEWING)
        await _interviewer(step_id, "question")


def _since_last(attempts: list[sqlite3.Row], kind: str) -> list[sqlite3.Row]:
    marks = [i for i, a in enumerate(attempts) if a["kind"] == kind]
    return attempts[marks[-1] + 1 :] if marks else attempts


def _hints_since_progress(attempts: list[sqlite3.Row]) -> int:
    marks = [
        i
        for i, a in enumerate(attempts)
        if a["kind"] == "answer" and json.loads(a["grader_json"])["improved"]
    ]
    later = attempts[marks[-1] + 1 :] if marks else attempts
    return sum(a["kind"] == "hint" for a in later)


async def hint(step_id: int) -> None:
    with db.session() as conn:
        _current(conn, step_id, S.INTERVIEWING)
        attempts = _attempts(conn, step_id)
        if not any(a["kind"] == "answer" for a in attempts):
            raise Conflict("Answer the question first; hints come after an answer.")
        level = rubric.hint_level(_hints_since_progress(attempts))
        conn.execute(
            "INSERT INTO attempts (step_id, kind, content) VALUES (?, 'hint', ?)",
            (step_id, f"level {level}"),
        )
    _advance(step_id, S.INTERVIEWING)
    await _interviewer(step_id, f"hint level {level}")


async def reteach(step_id: int) -> None:
    with db.session() as conn:
        step = _current(conn, step_id, S.INTERVIEWING)
        missing = [r["text"] for r in _items(conn, step_id) if r["status"] != "covered"]
        msg = user_message(
            tag("mode", "reteach"),
            _plan_block(conn, step["project_id"]),
            _step_block(step),
            tag("lesson", _lesson(conn, step_id) or ""),
            tag("missing_points", "\n".join(f"- {m}" for m in missing)),
            tag("answers", "\n\n".join(_answers(conn, step_id))),
        )
    text = await client.text(
        "tutor", msg, project_id=step["project_id"], step_id=step_id, stream=True
    )
    with db.session() as conn:
        _say(conn, step, "tutor", "reteach", text)
        conn.execute(
            "INSERT INTO attempts (step_id, kind, content) VALUES (?, 'reteach', '')", (step_id,)
        )
    _advance(step_id, S.INTERVIEWING)
    await _interviewer(step_id, "resume")


# ---- views


def step_view(step_id: int) -> dict[str, Any]:
    with db.session() as conn:
        step = _step(conn, step_id)
        items = [Item(r["text"], r["status"]) for r in _items(conn, step_id)]
        attempts = _attempts(conn, step_id)
        return {
            "id": step["id"],
            "project_id": step["project_id"],
            "position": step["position"],
            "title": step["title"],
            "component": step["component"],
            "goal": step["goal"],
            "concepts": json.loads(step["concepts"]),
            "state": step["state"],
            "current": current_step_id(conn, step["project_id"]) == step_id,
            "lesson": _lesson(conn, step_id),
            "build_note": json.loads(step["build_note"]) if step["build_note"] else None,
            "review_note": json.loads(step["review_note"]) if step["review_note"] else None,
            "tour": json.loads(step["tour_json"]) if step["tour_json"] else None,
            "chat": [dict(m) for m in _messages(conn, step_id, CHAT)],
            "gate": [dict(m) for m in _messages(conn, step_id, GATE)],
            "progress": rubric.progress(items),
            "can_hint": step["state"] == S.INTERVIEWING
            and any(a["kind"] == "answer" for a in attempts),
        }
