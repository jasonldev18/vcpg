from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.orchestrator import build, runner

router = APIRouter(prefix="/api/steps")

Text = Field(min_length=1, max_length=5_000)


class Advance(BaseModel):
    action: Literal["ready", "build", "retry", "stop", "pause", "resume", "ready_for_interview"]


class Question(BaseModel):
    question: str = Text


class Answer(BaseModel):
    answer: str = Text


def view(step_id: int) -> dict[str, Any]:
    return runner.step_view(step_id) | {"build": build.status(step_id)}


@router.get("/{step_id}")
def get(step_id: int) -> dict[str, Any]:
    return view(step_id)


@router.post("/{step_id}/teach")
async def teach(step_id: int) -> dict[str, Any]:
    await runner.teach(step_id)
    return view(step_id)


@router.post("/{step_id}/tour")
async def tour(step_id: int) -> dict[str, Any]:
    await runner.tour(step_id)
    return view(step_id)


@router.get("/{step_id}/file")
def file(step_id: int, path: str) -> dict[str, Any]:
    return {"path": path, "lines": runner.file_at_commit(step_id, path)}


@router.post("/{step_id}/ask")
async def ask(step_id: int, body: Question) -> dict[str, Any]:
    await runner.ask(step_id, body.question)
    return view(step_id)


@router.post("/{step_id}/advance")
async def advance(step_id: int, body: Advance) -> dict[str, Any]:
    match body.action:
        case "ready":
            build.ready(step_id)
        case "build":
            build.start(step_id)
        case "retry":
            build.retry(step_id)
        case "stop":
            build.stop(step_id)
        case "pause" | "resume":
            build.pause(step_id, paused=body.action == "pause")
        case "ready_for_interview":
            await runner.start_interview(step_id)
    return view(step_id)


@router.post("/{step_id}/gate/answer")
async def answer(step_id: int, body: Answer) -> dict[str, Any]:
    await runner.answer(step_id, body.answer)
    return view(step_id)


@router.post("/{step_id}/gate/hint")
async def hint(step_id: int) -> dict[str, Any]:
    await runner.hint(step_id)
    return view(step_id)


@router.post("/{step_id}/gate/reteach")
async def reteach(step_id: int) -> dict[str, Any]:
    await runner.reteach(step_id)
    return view(step_id)
