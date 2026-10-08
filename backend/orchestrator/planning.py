"""Brief → clarifying questions → plan → user edits → approve (SPEC section 4)."""

import json
import sqlite3
from typing import Any

from backend import db
from backend.errors import Conflict, NotFound
from backend.llm import client
from backend.orchestrator.context import history, tag, user_message
from backend.schemas import Plan, PlanStep
from backend.workspace import git


def project_row(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise NotFound(f"Project {project_id} does not exist.")
    return row


def _planning(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row:
    project = project_row(conn, project_id)
    if project["status"] != "planning":
        raise Conflict("The plan is already approved.")
    return project


def _draft_of(project: sqlite3.Row) -> Plan:
    if project["plan_json"] is None:
        raise Conflict("There is no draft plan yet.")
    return Plan.model_validate_json(project["plan_json"])


def _save(conn: sqlite3.Connection, project_id: int, plan: Plan) -> None:
    name = plan.project_name if not plan.questions else "New project"
    conn.execute(
        "UPDATE projects SET plan_json = ?, name = ? WHERE id = ?",
        (plan.model_dump_json(), name, project_id),
    )


async def _draft(project_id: int, change_request: str | None = None) -> None:
    with db.session() as conn:
        project = _planning(conn, project_id)
        answers = [
            r["content"]
            for r in conn.execute(
                "SELECT content FROM messages WHERE project_id = ? AND agent = 'planner'"
                " AND role = 'user' ORDER BY id",
                (project_id,),
            )
        ]
        blocks = [tag("brief", project["brief"]), tag("history", history(conn, project_id))]
        if answers:
            blocks.append(tag("answers", "\n\n".join(answers)))
        if change_request is not None:
            current = _draft_of(project)
            blocks += [
                tag("current_plan", current.model_dump_json(indent=1)),
                tag("change_request", change_request),
            ]
    plan = await client.structured("planner", user_message(*blocks), Plan, project_id=project_id)
    with db.session() as conn:
        _save(conn, project_id, plan)


async def create(brief: str) -> int:
    with db.session() as conn:
        project_id = conn.execute(
            "INSERT INTO projects (name, brief, start_path) VALUES ('New project', ?, 'plan')",
            (brief,),
        ).lastrowid
    assert project_id is not None
    try:
        await _draft(project_id)
    except Exception:
        with db.session() as conn:  # no draft means no project; the user retries from Start
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        raise
    return project_id


async def answer_questions(project_id: int, answers: list[str]) -> None:
    with db.session() as conn:
        questions = _draft_of(_planning(conn, project_id)).questions
        if len(answers) != len(questions):
            raise Conflict(f"Expected {len(questions)} answers.")
        qa = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in zip(questions, answers, strict=True))
        conn.execute(
            "INSERT INTO messages (project_id, agent, role, content)"
            " VALUES (?, 'planner', 'user', ?)",
            (project_id, qa),
        )
    await _draft(project_id)


async def revise(project_id: int, request: str) -> None:
    await _draft(project_id, change_request=request)


def edit(project_id: int, order: list[tuple[int, str]]) -> None:
    """Reorder, rename or drop steps. `order` lists (index in the draft, title) to keep."""
    with db.session() as conn:
        plan = _draft_of(_planning(conn, project_id))
        sources = [source for source, _ in order]
        if len(set(sources)) != len(sources) or not all(0 <= s < len(plan.steps) for s in sources):
            raise Conflict("Each step can appear once, and only steps from the draft.")
        if not order:
            raise Conflict("A plan needs at least one step.")
        steps = [plan.steps[s].model_copy(update={"title": title}) for s, title in order]
        _save(conn, project_id, plan.model_copy(update={"steps": steps}))


def _insert_steps(
    conn: sqlite3.Connection, project_id: int, steps: list[PlanStep], start: int
) -> None:
    for position, step in enumerate(steps, start):
        step_id = conn.execute(
            "INSERT INTO steps (project_id, position, title, component, goal, concepts,"
            " files, acceptance) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                position,
                step.title,
                step.component,
                step.goal,
                json.dumps(step.concepts),
                json.dumps(step.files),
                json.dumps(step.acceptance),
            ),
        ).lastrowid
        conn.executemany(
            "INSERT INTO rubric_items (step_id, text) VALUES (?, ?)",
            [(step_id, item) for item in step.rubric],
        )


def approve(project_id: int) -> None:
    with db.session() as conn:
        plan = _draft_of(_planning(conn, project_id))
        if plan.questions or not plan.steps:
            raise Conflict("Answer the planner's questions before approving.")
        _insert_steps(conn, project_id, plan.steps, 0)
        workspace = git.init(project_id, plan.project_name)  # a failure rolls the approval back
        conn.execute(
            "UPDATE projects SET status = 'active', workspace_path = ? WHERE id = ?",
            (str(workspace), project_id),
        )


PASSED = ("passed", "slide_done")


def _steps_as_plan(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[PlanStep]:
    return [
        PlanStep(
            title=r["title"],
            component=r["component"],
            goal=r["goal"],
            concepts=json.loads(r["concepts"]),
            files=json.loads(r["files"]),
            acceptance=json.loads(r["acceptance"]),
            rubric=[
                i["text"]
                for i in conn.execute(
                    "SELECT text FROM rubric_items WHERE step_id = ? ORDER BY id", (r["id"],)
                )
            ],
        )
        for r in rows
    ]


def _open_steps(conn: sqlite3.Connection, project_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM steps WHERE project_id = ? AND state NOT IN (?, ?) ORDER BY position",
        (project_id, *PASSED),
    ).fetchall()


async def propose_replan(project_id: int, request: str) -> None:
    """Revise the steps not yet passed (SPEC section 4). The user approves or discards it."""
    with db.session() as conn:
        project = project_row(conn, project_id)
        if project["status"] != "active":
            raise Conflict("Only an active project's plan can be revised.")
        passed = conn.execute(
            "SELECT title FROM steps WHERE project_id = ? AND state IN (?, ?) ORDER BY position",
            (project_id, *PASSED),
        ).fetchall()
        rows = _open_steps(conn, project_id)
        notes = [
            f"Step '{r['title']}' is blocked.\nBuild note: {r['build_note']}\n"
            f"Review note: {r['review_note']}"
            for r in rows
            if r["state"] == "blocked"
        ]
        current = [s.model_dump() for s in _steps_as_plan(conn, rows)]
        blocks = [
            tag("brief", project["brief"]),
            tag("passed_steps", "\n".join(r["title"] for r in passed) or "none"),
            tag("current_plan", json.dumps(current, indent=1)),
            tag("change_request", "\n\n".join([request, *notes])),
        ]
    plan = await client.structured("planner", user_message(*blocks), Plan, project_id=project_id)
    with db.session() as conn:
        conn.execute(
            "UPDATE projects SET replan_json = ? WHERE id = ?", (plan.model_dump_json(), project_id)
        )


def apply_replan(project_id: int) -> None:
    """Replace every unpassed step with the revision. Passed steps are never rewritten."""
    with db.session() as conn:
        project = project_row(conn, project_id)
        if project["replan_json"] is None:
            raise Conflict("There is no plan revision to approve.")
        plan = Plan.model_validate_json(project["replan_json"])
        if not plan.steps:
            raise Conflict("The revision has no steps.")
        start = conn.execute(
            "SELECT COUNT(*) FROM steps WHERE project_id = ? AND state IN (?, ?)",
            (project_id, *PASSED),
        ).fetchone()[0]
        conn.executemany(
            "DELETE FROM steps WHERE id = ?", [(r["id"],) for r in _open_steps(conn, project_id)]
        )
        _insert_steps(conn, project_id, plan.steps, start)
        conn.execute("UPDATE projects SET replan_json = NULL WHERE id = ?", (project_id,))


def discard_replan(project_id: int) -> None:
    with db.session() as conn:
        conn.execute("UPDATE projects SET replan_json = NULL WHERE id = ?", (project_id,))


def replan_view(conn: sqlite3.Connection, project: sqlite3.Row) -> dict[str, Any] | None:
    if project["replan_json"] is None:
        return None
    new = public_plan(Plan.model_validate_json(project["replan_json"]))
    old = [{"title": r["title"], "goal": r["goal"]} for r in _open_steps(conn, project["id"])]
    return {"old": old, "new": new["steps"], "changes": new["changes_from_spine"]}


def public_plan(plan: Plan) -> dict[str, Any]:
    """What the user may see of a draft: never the rubrics (SPEC section 4)."""
    return {
        "questions": plan.questions,
        "project_name": plan.project_name,
        "one_liner": plan.one_liner,
        "stack": plan.stack,
        "changes_from_spine": [c.model_dump() for c in plan.changes_from_spine],
        "steps": [
            {"title": s.title, "goal": s.goal, "concepts": s.concepts, "component": s.component}
            for s in plan.steps
        ],
    }
