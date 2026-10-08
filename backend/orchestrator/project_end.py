"""After the last step: final review, re-test, deck, then README (SPEC section 6)."""

import asyncio
import json
import sqlite3
from typing import Any

from backend import db
from backend.errors import Conflict
from backend.events import bus
from backend.gate import rubric
from backend.gate.rubric import Item
from backend.llm import client, sdk
from backend.orchestrator import runner, slides
from backend.orchestrator.context import tag, user_message
from backend.orchestrator.machine import State
from backend.orchestrator.planning import project_row
from backend.redact import redact
from backend.schemas import GateGrade, ReviewNote
from backend.workspace import git

S = State
NEXT_STAGE = {"final_review": "retest", "retest": "deck", "deck": "readme", "readme": "done"}


def _project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row:
    return project_row(conn, project_id)


def _stage(conn: sqlite3.Connection, project_id: int, *expected: str) -> sqlite3.Row:
    project = _project(conn, project_id)
    if project["finish_stage"] not in expected:
        raise Conflict(f"The project is at {project['finish_stage'] or 'its steps'}.")
    return project


def _advance_stage(conn: sqlite3.Connection, project_id: int, stage: str) -> None:
    status = "done" if stage == "done" else "finishing"
    conn.execute(
        "UPDATE projects SET finish_stage = ?, status = ?,"
        " finished_at = CASE WHEN ? = 'done' THEN CURRENT_TIMESTAMP END WHERE id = ?",
        (stage, status, stage, project_id),
    )
    bus.publish(project_id, "project_stage", stage=stage)


# ---- step completion


async def complete_step(step_id: int) -> None:
    """Gate passed: write the slide, mark the step done, and finish after the last step."""
    await slides.write_step_slide(step_id)
    runner._advance(step_id, S.SLIDE_DONE)
    with db.session() as conn:
        project_id = runner._step(conn, step_id)["project_id"]
        if runner.current_step_id(conn, project_id) is None:
            _advance_stage(conn, project_id, "final_review")


# ---- final review


_final: dict[int, asyncio.Task[None]] = {}
_final_errors: dict[int, str] = {}


def final_status(project_id: int) -> dict[str, Any]:
    task = _final.get(project_id)
    return {
        "running": task is not None and not task.done(),
        "error": _final_errors.get(project_id),
    }


def start_final_review(project_id: int) -> None:
    with db.session() as conn:
        _stage(conn, project_id, "final_review")
    if final_status(project_id)["running"]:
        raise Conflict("The final review is already running.")
    _final_errors.pop(project_id, None)
    _final[project_id] = asyncio.create_task(_final_review(project_id))


async def _final_review(project_id: int) -> None:
    try:
        with db.session() as conn:
            repo = runner._repo(conn, project_id)
            steps = conn.execute(
                "SELECT * FROM steps WHERE project_id = ? ORDER BY position", (project_id,)
            ).fetchall()
            task = "\n\n".join(
                [
                    tag("mode", "final"),
                    runner._plan_block(conn, project_id),
                    *(
                        tag("step", f"{s['title']}: {s['goal']}\n{runner.build_summary(s)}")
                        for s in steps
                    ),
                ]
            )
        go = asyncio.Event()
        go.set()
        review = await sdk.run_agent(
            "reviewer", task, repo, ReviewNote,
            project_id=project_id, step_id=steps[-1]["id"], allow_install=False, resume=go,
        )  # fmt: skip
        with db.session() as conn:
            conn.execute(
                "UPDATE projects SET final_review_json = ? WHERE id = ?",
                (review.model_dump_json(), project_id),
            )
            if review.status == "pass":
                git.commit(repo, "final review")
                _start_retest(conn, project_id)
                _advance_stage(conn, project_id, "retest")
    except Exception as e:
        _final_errors[project_id] = redact(str(e))
        bus.publish(
            project_id, "project_stage", stage="final_review", error=_final_errors[project_id]
        )


# ---- re-test: one question per step, on the point that was hardest at its gate


def _start_retest(conn: sqlite3.Connection, project_id: int) -> None:
    items = []
    for step in conn.execute(
        "SELECT id, title FROM steps WHERE project_id = ? ORDER BY position", (project_id,)
    ).fetchall():
        texts = [r["text"] for r in runner._items(conn, step["id"])]
        states = rubric.replay(texts, runner.graded_answers(conn, step["id"]))
        hardest = rubric.hardest(states, len(texts))
        items.append(
            {
                "step_id": step["id"],
                "title": step["title"],
                "item": texts[hardest],
                "status": "pending",
            }
        )
    conn.execute(
        "UPDATE projects SET retest_json = ? WHERE id = ?",
        (json.dumps({"items": items}), project_id),
    )


def _retest(
    conn: sqlite3.Connection, project_id: int
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    items: list[dict[str, Any]] = json.loads(_project(conn, project_id)["retest_json"])["items"]
    return items, next((i for i in items if i["status"] == "pending"), None)


def _retest_messages(conn: sqlite3.Connection, step_id: int) -> list[sqlite3.Row]:
    return runner._messages(conn, step_id, "agent = 'retest'")


def _say(conn: sqlite3.Connection, project_id: int, step_id: int, role: str, text: str) -> None:
    conn.execute(
        "INSERT INTO messages (project_id, step_id, agent, role, content)"
        " VALUES (?, ?, 'retest', ?, ?)",
        (project_id, step_id, role, text),
    )


async def _ask(project_id: int, item: dict[str, Any], request: str) -> None:
    with db.session() as conn:
        step = runner._step(conn, item["step_id"])
        msg = user_message(
            runner._step_block(step),
            tag("build_summary", runner.build_summary(step)),
            tag("rubric", f"0. {item['item']} [missing]"),
            tag("gap", "This is the end-of-project re-test: one question on this point."),
            tag("conversation", runner._transcript(_retest_messages(conn, step["id"]))),
            tag("request", request),
        )
    question = await client.text("interviewer", msg, project_id=project_id, stream=True)
    with db.session() as conn:
        _say(conn, project_id, item["step_id"], "assistant", question)


async def retest_start(project_id: int) -> None:
    with db.session() as conn:
        _stage(conn, project_id, "retest")
        _, item = _retest(conn, project_id)
        if item is None or _retest_messages(conn, item["step_id"]):
            return
    await _ask(project_id, item, "question")


async def retest_answer(project_id: int, text: str) -> None:
    with db.session() as conn:
        _stage(conn, project_id, "retest")
        items, item = _retest(conn, project_id)
        if item is None:
            raise Conflict("The re-test is finished.")
        _say(conn, project_id, item["step_id"], "user", text)
        step = runner._step(conn, item["step_id"])
        rows = _retest_messages(conn, step["id"])
        answers = [m["content"] for m in rows if m["role"] == "user"]
        msg = runner.grader_message(
            [item["item"]],
            runner._step_block(step),
            runner.build_summary(step),
            answers,
            [m["content"] for m in rows if m["role"] == "assistant"],
        )
    grade = await client.structured("grader", msg, GateGrade, project_id=project_id)
    covered = rubric.passed(rubric.merge([Item(item["item"])], grade, answers))
    if not covered:  # a miss re-teaches that step only, then asks again
        await _reteach(project_id, item, answers)
        await _ask(project_id, item, "resume")
        return
    with db.session() as conn:
        item["status"] = "passed"
        conn.execute(
            "UPDATE projects SET retest_json = ? WHERE id = ?",
            (json.dumps({"items": items}), project_id),
        )
        bus.publish(
            project_id,
            "gate_update",
            covered=sum(i["status"] == "passed" for i in items),
            total=len(items),
        )
        _, following = _retest(conn, project_id)
    if following is not None:
        await _ask(project_id, following, "question")
        return
    await slides.ensure_project_slides(project_id)
    with db.session() as conn:
        _advance_stage(conn, project_id, "deck")


async def _reteach(project_id: int, item: dict[str, Any], answers: list[str]) -> None:
    with db.session() as conn:
        step = runner._step(conn, item["step_id"])
        msg = user_message(
            tag("mode", "reteach"),
            runner._plan_block(conn, project_id),
            runner._step_block(step),
            tag("lesson", runner._lesson(conn, step["id"]) or ""),
            tag("missing_points", f"- {item['item']}"),
            tag("answers", "\n\n".join(answers)),
        )
    text = await client.text("tutor", msg, project_id=project_id, stream=True)
    with db.session() as conn:
        _say(conn, project_id, item["step_id"], "reteach", text)


async def prepare_deck(project_id: int) -> None:
    """Retry writing the title, overview and retrospective slides if that failed."""
    with db.session() as conn:
        _stage(conn, project_id, "retest", "deck")
        _, item = _retest(conn, project_id)
        if item is not None:
            raise Conflict("Finish the re-test first.")
    await slides.ensure_project_slides(project_id)
    with db.session() as conn:
        if _project(conn, project_id)["finish_stage"] == "retest":
            _advance_stage(conn, project_id, "deck")


def deck_done(project_id: int) -> None:
    with db.session() as conn:
        _stage(conn, project_id, "deck")
        _advance_stage(conn, project_id, "readme")


def view(project_id: int) -> dict[str, Any] | None:
    with db.session() as conn:
        project = _project(conn, project_id)
        if project["finish_stage"] is None:
            return None
        out: dict[str, Any] = {
            "stage": project["finish_stage"],
            "final_review": json.loads(project["final_review_json"])
            if project["final_review_json"]
            else None,
            "final_review_status": final_status(project_id),
            "retest": None,
        }
        if project["retest_json"]:
            items, item = _retest(conn, project_id)
            out["retest"] = {
                "passed": sum(i["status"] == "passed" for i in items),
                "total": len(items),
                "current_step": item["title"] if item else None,
                "messages": [dict(m) for m in _retest_messages(conn, item["step_id"])]
                if item
                else [],
            }
    return out
