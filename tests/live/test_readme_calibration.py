"""Live: the README coach flags every planted mismatch with what the project shows, and never
returns rewritten README text."""

import pytest

from backend import secrets
from backend.audit import testsets

pytestmark = pytest.mark.live


async def test_coach_flags_planted_mismatches_without_rewriting() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    scores = await testsets.readme()
    print(scores)
    assert all(scores.values())
