"""Live: the README coach flags every planted mismatch with what the project shows, and never
returns rewritten README text."""

import pytest
import yaml
from pydantic import BaseModel

from backend import secrets
from backend.llm import client
from backend.orchestrator.context import tag, user_message
from backend.paths import REPO_ROOT
from backend.schemas import ReadmeReview

pytestmark = pytest.mark.live


class Planted(BaseModel):
    line: int
    shows: list[str]


class ReadmeCase(BaseModel):
    project: str
    readme: str
    planted: list[Planted]


async def test_coach_flags_planted_mismatches_without_rewriting() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    problems = []
    for path in sorted((REPO_ROOT / "calibration" / "readme").glob("*.yaml")):
        case = ReadmeCase.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(case.readme.splitlines(), 1))
        message = user_message(
            tag("mode", "review"), tag("project", case.project), tag("readme", numbered)
        )
        review = await client.structured("readme_coach", message, ReadmeReview)
        print(f"\n{path.stem}:")
        for n in review.notes:
            print(f"  line {n.line} {n.kind}: {n.note} | project shows: {n.project_shows}")
        for planted in case.planted:
            hits = [
                n
                for n in review.notes
                if n.kind == "does_not_match"
                and abs(n.line - planted.line) <= 1
                and any(word.lower() in n.project_shows.lower() for word in planted.shows)
            ]
            if not hits:
                problems.append(
                    f"{path.stem}: line {planted.line} was not flagged with {planted.shows}"
                )
        for n in review.notes:  # notes explain; they must not hand back README text to paste
            if "\n#" in n.note or "```" in n.note or len(n.note.split()) > 80:
                problems.append(f"{path.stem}: line {n.line} note looks like rewritten text")
    print("\n".join(problems) or "\nall planted mismatches flagged")
    assert not problems
