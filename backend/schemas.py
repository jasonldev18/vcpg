"""Structured outputs from agents (AGENTS.md). Each is sent to the model as a JSON schema."""

import json
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, ValidationError, model_validator

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


class CommandRun(BaseModel):
    cmd: str
    result: Literal["pass", "fail"]
    summary: str


class Cut(BaseModel):
    path: str
    what: str
    why: str


class Fix(BaseModel):
    path: str
    what: str


class ReviewNote(BaseModel):
    commands: list[CommandRun]
    cut: list[Cut]
    fixed: list[Fix]
    status: Literal["pass", "fail"]
    failure: str | None


class TourStop(BaseModel):
    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    explanation: str


class Tour(BaseModel):
    stops: list[TourStop] = Field(min_length=1)


# ---- slides (AGENTS.md slide writer, DESIGN.md section 6)


class Node(BaseModel):
    id: str
    label: str
    group: str


class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    label: str

    model_config = {"populate_by_name": True}


class ArchitectureSpec(BaseModel):
    nodes: list[Node] = Field(min_length=1, max_length=12)
    edges: list[Edge]


class FlowSpec(BaseModel):
    steps: list[str] = Field(min_length=2, max_length=7)


class Series(BaseModel):
    name: str
    x: list[float | str]
    y: list[float]


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "scatter"]
    series: list[Series] = Field(min_length=1)
    x_label: str
    y_label: str


class CodeSpec(BaseModel):
    path: str
    lines: list[int] = Field(min_length=2, max_length=2)
    highlight: list[int]


class TableSpec(BaseModel):
    columns: list[str] = Field(min_length=1)
    rows: list[list[str]] = Field(max_length=5)


class ArchitectureVisual(BaseModel):
    kind: Literal["architecture"]
    spec: ArchitectureSpec


class FlowVisual(BaseModel):
    kind: Literal["flow"]
    spec: FlowSpec


class ChartVisual(BaseModel):
    kind: Literal["chart"]
    spec: ChartSpec


class CodeVisual(BaseModel):
    kind: Literal["code"]
    spec: CodeSpec


class TableVisual(BaseModel):
    kind: Literal["table"]
    spec: TableSpec


Visual = Annotated[
    ArchitectureVisual | FlowVisual | ChartVisual | CodeVisual | TableVisual,
    Field(discriminator="kind"),
]


class Decision(BaseModel):
    choice: str
    tradeoff: str


class Struggle(BaseModel):
    question: str
    hints: int = Field(ge=0)


class Slide(BaseModel):
    title: str
    kicker: str
    what: str
    visual: Visual
    decisions: list[Decision] = Field(max_length=4)
    failure_and_scale: list[str] = Field(max_length=3)
    struggled: list[Struggle]
    notes: str


class VisualDraft(BaseModel):
    kind: Literal["architecture", "flow", "chart", "code", "table"]
    spec_json: str  # the spec as JSON text: one typed schema per kind is too large for the API


class SlideDraft(BaseModel):
    """What the slide writer returns; validated into a Slide, so a bad spec triggers a retry."""

    title: str
    kicker: str
    what: str
    visual: VisualDraft
    decisions: list[Decision]
    failure_and_scale: list[str]
    struggled: list[Struggle]
    notes: str

    def to_slide(self) -> Slide:
        data = self.model_dump()
        data["visual"] = {"kind": self.visual.kind, "spec": json.loads(self.visual.spec_json)}
        return Slide.model_validate(data)

    @model_validator(mode="after")
    def spec_matches_kind(self) -> Self:
        try:
            self.to_slide()
        except (ValueError, ValidationError) as e:
            raise ValueError(f"visual.spec_json does not fit kind {self.visual.kind}: {e}") from e
        return self


class ReadmeNote(BaseModel):
    line: int
    kind: Literal["does_not_match", "gap", "unclear"]
    note: str
    project_shows: str


class ReadmeReview(BaseModel):
    notes: list[ReadmeNote]


Dimension = Literal["system_design", "failure_modes", "motivation_and_impact", "communication"]


class DimensionScore(BaseModel):
    name: Dimension
    score: int = Field(ge=1, le=5)
    evidence: str | None
    reason: str


class Scorecard(BaseModel):
    dimensions: list[DimensionScore] = Field(min_length=4, max_length=4)
    practise: list[str]


# ---- discovery: lessons (SPEC section 9) and ideas (SPEC section 3.2)

SectionKind = Literal[
    "start_here", "see_it", "worked_example", "check_yourself", "your_turn", "recap"
]


class LessonOutline(BaseModel):
    title: str
    goal: str
    key_terms: list[str]


class LessonPath(BaseModel):
    lessons: list[LessonOutline] = Field(min_length=4, max_length=8)


class Paragraph(BaseModel):
    text: str
    citations: list[str]


class Option(BaseModel):
    text: str
    correct: bool
    why: str


class Question(BaseModel):
    type: Literal["mc", "tf", "short", "code"]
    prompt: str
    options: list[Option]  # mc and tf
    answer: str  # model answer for short; starter code for code
    rubric: list[str]  # short: points a good answer covers
    tests: str  # code: pytest tests the learner's solution must pass


class Section(BaseModel):
    kind: SectionKind
    paragraphs: list[Paragraph]
    visual_json: str  # see_it: a slide-style visual as JSON text, "" otherwise
    code: str  # worked_example: the snippet, "" otherwise
    questions: list[Question]


class CommunityNote(BaseModel):
    text: str
    source_id: str


class Lesson(BaseModel):
    title: str
    by_the_end: list[str]
    sections: list[Section]
    community: list[CommunityNote]


class Thumbnail(BaseModel):
    template: Literal["chat", "ranked", "cluster", "code_hits", "chart", "pipeline"]
    data_json: str


class IdeaConcept(BaseModel):
    name: str
    familiarity: Literal["new", "basics", "used"]


class IdeaCard(BaseModel):
    name: str
    line: str
    pitch: str
    difficulty: Literal["gentle", "medium", "stretch"]
    step_count: int = Field(ge=3, le=10)
    thumbnail: Thumbnail
    concepts: list[IdeaConcept] = Field(min_length=3, max_length=5)
    architecture: list[str] = Field(min_length=3, max_length=6)
    questions: list[str]


class IdeaBatch(BaseModel):
    cards: list[IdeaCard] = Field(min_length=4, max_length=4)


# ---- audit crew (AGENTS.md)


class Evidence(BaseModel):
    call_id: int
    excerpt: str


class AuditIssue(BaseModel):
    title: str
    severity: Literal["low", "medium", "high"]
    agent: str
    evidence: list[Evidence]
    suspected_cause: str
    suggested_fix: str


class AuditReport(BaseModel):
    issues: list[AuditIssue]


class NewFile(BaseModel):
    path: str
    content: str  # the whole file after the change


class RookFix(BaseModel):
    slug: str
    title: str
    issues: list[str]  # titles of the scout issues this fixes
    problem: str
    evidence: list[str]
    change: str
    files: list[NewFile] = Field(min_length=1)
    risk: Literal["auto", "review"]


class RookPlan(BaseModel):
    fixes: list[RookFix]
