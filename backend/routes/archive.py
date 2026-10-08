"""README coach, archive, dossier and mock interviews."""

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend import db
from backend.orchestrator import mock, slides, wrapup

router = APIRouter(prefix="/api")


class ReadmeText(BaseModel):
    content: str = Field(max_length=100_000)


class MockStart(BaseModel):
    length_min: mock.Length
    focus: mock.Focus


class MockAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=5_000)


@router.get("/projects/{project_id}/readme")
def readme(project_id: int) -> dict[str, Any] | None:
    return wrapup.view(project_id)


@router.post("/projects/{project_id}/readme/template")
async def readme_template(project_id: int) -> dict[str, Any] | None:
    await wrapup.template(project_id)
    return wrapup.view(project_id)


@router.put("/projects/{project_id}/readme")
def save_readme(project_id: int, body: ReadmeText) -> dict[str, Any] | None:
    wrapup.save(project_id, body.content)
    return wrapup.view(project_id)


@router.post("/projects/{project_id}/readme/review")
async def review_readme(project_id: int) -> dict[str, Any] | None:
    await wrapup.review(project_id)
    return wrapup.view(project_id)


@router.post("/projects/{project_id}/readme/finish")
async def finish(project_id: int) -> dict[str, Any] | None:
    await wrapup.finish(project_id)
    return wrapup.view(project_id)


@router.get("/archive")
def archive() -> list[dict[str, Any]]:
    with db.session() as conn:
        rows = conn.execute(
            "SELECT p.id, p.name, p.plan_json, p.finished_at, d.markdown AS dossier,"
            " r.content AS readme FROM projects p"
            " LEFT JOIN dossiers d ON d.project_id = p.id"
            " LEFT JOIN readmes r ON r.project_id = p.id"
            " WHERE p.status = 'done' ORDER BY p.finished_at DESC"
        ).fetchall()
        mocks = conn.execute(
            "SELECT id, project_id, length_min, focus, started_at FROM mock_interviews"
            " ORDER BY id DESC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "stack": json.loads(r["plan_json"])["stack"],
            "finished_at": r["finished_at"],
            "dossier": r["dossier"],
            "readme": r["readme"],
            "exports": slides.exports(r["id"]),
            "mocks": [dict(m) for m in mocks if m["project_id"] == r["id"]],
        }
        for r in rows
    ]


@router.post("/archive/{project_id}/mock")
async def start_mock(project_id: int, body: MockStart) -> dict[str, Any]:
    return mock.view(await mock.start(project_id, body.length_min, body.focus))


@router.get("/mock/{mock_id}")
def get_mock(mock_id: int) -> dict[str, Any]:
    return mock.view(mock_id)


@router.post("/mock/{mock_id}/answer")
async def mock_answer(mock_id: int, body: MockAnswer) -> dict[str, Any]:
    await mock.answer(mock_id, body.answer)
    return mock.view(mock_id)


@router.post("/mock/{mock_id}/end")
async def end_mock(mock_id: int) -> dict[str, Any]:
    await mock.end(mock_id)
    return mock.view(mock_id)
