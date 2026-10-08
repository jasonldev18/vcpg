from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend import db
from backend.errors import Conflict
from backend.orchestrator import build, planning, project_end, runner
from backend.schemas import Plan

router = APIRouter(prefix="/api/projects")

Text = Field(min_length=1, max_length=10_000)


class Brief(BaseModel):
    brief: str = Text


class Answers(BaseModel):
    answers: list[str] = Field(max_length=3)


class Revision(BaseModel):
    request: str = Text


class StepOrder(BaseModel):
    source: int
    title: str = Field(min_length=1, max_length=200)


class PlanEdit(BaseModel):
    steps: list[StepOrder]


def project_view(project_id: int) -> dict[str, Any]:
    with db.session() as conn:
        project = planning.project_row(conn, project_id)
        step_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM steps WHERE project_id = ? ORDER BY position", (project_id,)
            )
        ]
        current = runner.current_step_id(conn, project_id)
        replan = planning.replan_view(conn, project)
    draft = project["plan_json"] and Plan.model_validate_json(project["plan_json"])
    return {
        "id": project["id"],
        "name": project["name"],
        "brief": project["brief"],
        "status": project["status"],
        "plan": planning.public_plan(draft) if draft and project["status"] == "planning" else None,
        "steps": [runner.step_view(i) | {"chat": [], "gate": []} for i in step_ids],
        "current_step_id": current,
        "replan": replan,
        "finish": project_end.view(project_id),
    }


@router.post("")
async def create(body: Brief) -> dict[str, Any]:
    return project_view(await planning.create(body.brief))


@router.get("/current")
def current() -> dict[str, Any] | None:
    with db.session() as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE status != 'done' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return project_view(row["id"]) if row else None


@router.get("/{project_id}")
def get(project_id: int) -> dict[str, Any]:
    return project_view(project_id)


@router.post("/{project_id}/plan/answers")
async def answer(project_id: int, body: Answers) -> dict[str, Any]:
    await planning.answer_questions(project_id, body.answers)
    return project_view(project_id)


@router.post("/{project_id}/plan/revise")
async def revise(project_id: int, body: Revision) -> dict[str, Any]:
    await planning.revise(project_id, body.request)
    return project_view(project_id)


@router.put("/{project_id}/plan")
def edit(project_id: int, body: PlanEdit) -> dict[str, Any]:
    planning.edit(project_id, [(s.source, s.title) for s in body.steps])
    return project_view(project_id)


@router.post("/{project_id}/plan/approve")
def approve(project_id: int) -> dict[str, Any]:
    planning.approve(project_id)
    return project_view(project_id)


@router.post("/{project_id}/replan")
async def replan(project_id: int, body: Revision) -> dict[str, Any]:
    await planning.propose_replan(project_id, body.request)
    return project_view(project_id)


@router.post("/{project_id}/replan/approve")
def approve_replan(project_id: int) -> dict[str, Any]:
    with db.session() as conn:
        ids = [
            r["id"]
            for r in conn.execute("SELECT id FROM steps WHERE project_id = ?", (project_id,))
        ]
    if any(build.status(i)["running"] for i in ids):
        raise Conflict("Stop the running build before changing the plan.")
    planning.apply_replan(project_id)
    return project_view(project_id)


@router.delete("/{project_id}/replan")
def discard_replan(project_id: int) -> dict[str, Any]:
    planning.discard_replan(project_id)
    return project_view(project_id)


class Answer(BaseModel):
    answer: str = Field(min_length=1, max_length=5_000)


@router.post("/{project_id}/final-review")
async def final_review(project_id: int) -> dict[str, Any]:  # starts a task on the loop
    project_end.start_final_review(project_id)
    return project_view(project_id)


@router.post("/{project_id}/retest/start")
async def retest_start(project_id: int) -> dict[str, Any]:
    await project_end.retest_start(project_id)
    return project_view(project_id)


@router.post("/{project_id}/retest/answer")
async def retest_answer(project_id: int, body: Answer) -> dict[str, Any]:
    await project_end.retest_answer(project_id, body.answer)
    return project_view(project_id)


@router.post("/{project_id}/deck/prepare")
async def prepare_deck(project_id: int) -> dict[str, Any]:
    await project_end.prepare_deck(project_id)
    return project_view(project_id)


@router.post("/{project_id}/deck/done")
def deck_done(project_id: int) -> dict[str, Any]:
    project_end.deck_done(project_id)
    return project_view(project_id)
