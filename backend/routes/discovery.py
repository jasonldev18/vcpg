"""Give me ideas, Teach me a concept, and lesson sources."""

import asyncio
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend import db
from backend.lessons import builder, sources
from backend.orchestrator import ideas
from backend.routes.projects import project_view
from backend.schemas import SectionKind

router = APIRouter(prefix="/api")

Short = Field(min_length=1, max_length=300)


class IdeaRequest(BaseModel):
    topic: str = Short
    use: str = Field(default="", max_length=300)
    data: str = Field(default="", max_length=300)


class CardChoice(BaseModel):
    card: int


class LessonRequest(BaseModel):
    concept: str = Short


class LessonAnswer(BaseModel):
    lesson: int
    section: SectionKind
    question: int
    answer: str = Field(min_length=1, max_length=20_000)


class SourceUrl(BaseModel):
    url: str = Field(min_length=8, max_length=2_000)
    kind: sources.Kind = "trusted"


@router.post("/ideas")
async def make_ideas(body: IdeaRequest) -> dict[str, Any]:
    return ideas.view(await ideas.generate(body.topic, body.use, body.data))


@router.get("/ideas/{idea_id}")
def get_ideas(idea_id: int) -> dict[str, Any]:
    return ideas.view(idea_id)


@router.post("/ideas/{idea_id}/build")
async def build_idea(idea_id: int, body: CardChoice) -> dict[str, Any]:
    return project_view(await ideas.build(idea_id, body.card))


@router.post("/ideas/{idea_id}/teach")
async def teach_idea(idea_id: int, body: CardChoice) -> dict[str, Any]:
    return builder.view(await ideas.teach_first(idea_id, body.card))


@router.post("/lessons")
async def start_lesson_path(body: LessonRequest) -> dict[str, Any]:
    return builder.view(await builder.create_path(body.concept))


@router.get("/lessons")
def lesson_paths() -> list[dict[str, Any]]:
    with db.session() as conn:
        rows = conn.execute("SELECT id, concept, status FROM lessons ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


@router.get("/lessons/{lesson_id}")
def get_lesson_path(lesson_id: int) -> dict[str, Any]:
    return builder.view(lesson_id)


@router.post("/lessons/{lesson_id}/build/{index}")
async def build_lesson(lesson_id: int, index: int) -> dict[str, Any]:
    await builder.build_lesson(lesson_id, index)
    return builder.view(lesson_id)


@router.post("/lessons/{lesson_id}/answer")
async def answer(lesson_id: int, body: LessonAnswer) -> dict[str, Any]:
    return await builder.answer(lesson_id, body.lesson, body.section, body.question, body.answer)


@router.get("/sources")
def list_sources() -> list[dict[str, Any]]:
    with db.session() as conn:
        rows = conn.execute(
            "SELECT s.id, s.kind, s.title, s.url_or_path, s.added_by, COUNT(p.id) AS passages"
            " FROM sources s LEFT JOIN passages p ON p.source_id = s.id GROUP BY s.id ORDER BY s.id"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/sources/url")
async def add_url(body: SourceUrl) -> list[dict[str, Any]]:
    text = await asyncio.to_thread(sources.fetch, body.url)
    await asyncio.to_thread(sources.add, body.url, text, body.url, body.kind, "user")
    return list_sources()


@router.post("/sources/upload")
async def upload(
    request: Request, filename: str, kind: sources.Kind = "trusted"
) -> list[dict[str, Any]]:
    """The file is the raw request body, parsed here and never executed (SECURITY 8)."""
    data = await request.body()
    await asyncio.to_thread(sources.add_upload, filename, data, kind)
    return list_sources()
