"""Live: on calibration/slides/, no slide makes a claim the step bundle does not support."""

import asyncio
import re

import pytest

from backend import secrets
from backend.llm import client
from backend.orchestrator.context import tag, user_message
from backend.orchestrator.slides import step_message
from backend.schemas import Slide, SlideDraft
from tests.calibration import SlideBundle, slide_bundles

pytestmark = pytest.mark.live
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def claims(slide: Slide) -> str:
    """Every sentence the slide states, without hint counts and code line numbers."""
    visual = slide.visual
    parts = [slide.title, slide.kicker, slide.what, slide.notes, *slide.failure_and_scale]
    parts += [f"{d.choice} {d.tradeoff}" for d in slide.decisions]
    parts += [s.question for s in slide.struggled]
    if visual.kind == "architecture":
        parts += [n.label for n in visual.spec.nodes] + [e.label for e in visual.spec.edges]
    elif visual.kind == "flow":
        parts += visual.spec.steps
    elif visual.kind == "table":
        parts += visual.spec.columns + [c for row in visual.spec.rows for c in row]
    elif visual.kind == "chart":
        parts += [visual.spec.x_label, visual.spec.y_label]
        parts += [str(v) for s in visual.spec.series for v in [*s.x, *s.y]]
    return "\n".join(parts)


def problems(name: str, bundle: SlideBundle, slide: Slide) -> list[str]:
    source = "\n".join(bundle.model_dump(exclude={"forbidden"}).values())
    said = claims(slide)
    found = []
    for number in set(NUMBER.findall(said)):
        if number not in NUMBER.findall(source):
            found.append(f"{name}: number {number} is not in the bundle")
    for term in bundle.forbidden:
        if term.lower() in said.lower():
            found.append(f"{name}: unsupported claim '{term}'")
    if slide.visual.kind == "code" and slide.visual.spec.path not in bundle.code_files:
        found.append(f"{name}: code visual points at {slide.visual.spec.path}")
    return found


async def test_slides_only_claim_what_the_bundle_supports() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    bundles = slide_bundles()

    async def write(bundle: SlideBundle) -> Slide:
        message = step_message(
            tag("step", bundle.step), bundle.build_summary, bundle.build_note,
            bundle.review_note, bundle.code_files, bundle.gate,
        )  # fmt: skip
        draft = await client.structured("slide_writer", user_message(message), SlideDraft)
        return draft.to_slide()

    slides = await asyncio.gather(*(write(b) for b in bundles.values()))
    found = []
    for (name, bundle), slide in zip(bundles.items(), slides, strict=True):
        print(f"\n{name}:\n{slide.model_dump_json(indent=1, by_alias=True)}")
        found += problems(name, bundle, slide)
    print("\n".join(found) or "\nno unsupported claims")
    assert not found
