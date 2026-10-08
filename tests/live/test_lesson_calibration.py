"""Live: lessons for three concepts pass the validator, with no dropped sections in at least
two of them (sources are the seeded official docs, fetched on first use)."""

import pytest

from backend import secrets
from backend.lessons import builder

pytestmark = pytest.mark.live
CONCEPTS = ["k-nearest neighbours", "precision and recall", "embeddings for semantic search"]


async def test_three_concepts_build_with_at_most_one_dropping_sections() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    clean = 0
    for concept in CONCEPTS:
        lesson_id = await builder.create_path(concept)
        await builder.build_lesson(lesson_id, 0)
        first = builder.view(lesson_id)["lessons"][0]
        kinds = [s["kind"] for s in first["content"]["sections"]]
        print(f"\n{concept}: {first['title']}\n  kept {kinds}\n  dropped {first['dropped']}")
        clean += not first["dropped"]
    assert clean >= 2
