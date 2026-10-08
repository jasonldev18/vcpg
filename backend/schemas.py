"""Structured outputs from agents (AGENTS.md). Each is sent to the model as a JSON schema."""

from typing import Literal

from pydantic import BaseModel, Field

Component = Literal["frontend", "backend", "data", "llm", "infra", "evaluation"]
Status = Literal["missing", "partial", "covered"]


class PlanStep(BaseModel):
    title: str
    component: Component
    goal: str
    concepts: list[str]
    files: list[str]
    acceptance: list[str]
    rubric: list[str] = Field(min_length=3, max_length=5)


class SpineChange(BaseModel):
    step: str
    change: Literal["added", "skipped", "merged"]
    reason: str


class Plan(BaseModel):
    questions: list[str] = Field(max_length=3)
    project_name: str
    one_liner: str
    stack: list[str]
    steps: list[PlanStep]
    changes_from_spine: list[SpineChange]


class ItemGrade(BaseModel):
    item_index: int
    status: Status
    evidence: str | None
    reason: str


class GateGrade(BaseModel):
    items: list[ItemGrade]
    gap: str


class FileChange(BaseModel):
    path: str
    summary: str


class BuildNote(BaseModel):
    files: list[FileChange]
    decisions: list[str]
    not_done: list[str]
