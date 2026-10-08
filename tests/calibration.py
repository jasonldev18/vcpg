from pathlib import Path

import yaml
from pydantic import BaseModel

from backend.paths import REPO_ROOT
from backend.schemas import Status

GATE_SETS = REPO_ROOT / "calibration" / "gate"
STYLES = {
    "strong",
    "shallow",
    "wrong_but_confident",
    "off_topic",
    "partially_right",
    "copied_jargon",
}


class CalibrationStep(BaseModel):
    title: str
    component: str
    goal: str
    concepts: list[str]


class GradedAnswer(BaseModel):
    style: str
    text: str
    expected: list[Status]


class GateSet(BaseModel):
    step: CalibrationStep
    build_summary: str
    question: str
    rubric: list[str]
    answers: list[GradedAnswer]


def gate_sets() -> dict[str, GateSet]:
    return {
        path.stem: GateSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(Path(GATE_SETS).glob("*.yaml"))
    }


REVIEWER_SETS = REPO_ROOT / "calibration" / "reviewer"


class ReviewerStep(BaseModel):
    title: str
    goal: str
    files: list[str]
    acceptance: list[str]


class Marker(BaseModel):
    file: str
    marker: str


class ReviewerCase(BaseModel):
    step: ReviewerStep
    build_note: str
    unreachable: list[Marker]
    boundary: list[Marker]
    files: list[Path] = []


def reviewer_cases() -> dict[str, ReviewerCase]:
    cases = {}
    for folder in sorted(p for p in REVIEWER_SETS.iterdir() if p.is_dir()):
        case = ReviewerCase.model_validate(
            yaml.safe_load((folder / "case.yaml").read_text(encoding="utf-8"))
        )
        case.files = sorted(folder.glob("*.py"))
        cases[folder.name] = case
    return cases
