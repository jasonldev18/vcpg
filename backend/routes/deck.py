import asyncio
from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.orchestrator import slides
from backend.schemas import Slide

router = APIRouter(prefix="/api")


class Order(BaseModel):
    slide_ids: list[int]


class Instruction(BaseModel):
    instruction: str = Field(min_length=1, max_length=2_000)


class ExportRequest(BaseModel):
    format: slides.Format


def deck_view(project_id: int) -> dict[str, Any]:
    return {"slides": slides.deck(project_id), "exports": slides.exports(project_id)}


@router.get("/projects/{project_id}/deck")
def get_deck(project_id: int) -> dict[str, Any]:
    return deck_view(project_id)


@router.post("/projects/{project_id}/deck/order")
def reorder(project_id: int, body: Order) -> dict[str, Any]:
    slides.reorder(project_id, body.slide_ids)
    return deck_view(project_id)


@router.put("/slides/{slide_id}")
def edit(slide_id: int, body: Slide) -> dict[str, bool]:
    slides.edit(slide_id, body)
    return {"ok": True}


@router.post("/slides/{slide_id}/regenerate")
async def regenerate(slide_id: int, body: Instruction) -> dict[str, bool]:
    await slides.regenerate(slide_id, body.instruction)
    return {"ok": True}


@router.post("/projects/{project_id}/deck/export")
async def export(project_id: int, body: ExportRequest) -> dict[str, Any]:
    await asyncio.to_thread(slides.export_deck, project_id, body.format)
    return deck_view(project_id)


@router.get("/exports/{export_id}/download")
def download(export_id: int) -> FileResponse:
    path = slides.export_path(export_id)
    return FileResponse(path, filename=path.name)
