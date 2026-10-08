"""Live: on calibration/reviewer/, every planted unreachable branch is cut and every real
boundary check is kept, by the real reviewer, through the same task the app builds."""

import pytest

from backend import secrets
from backend.audit import testsets

pytestmark = pytest.mark.live


async def test_reviewer_cuts_unreachable_code_and_keeps_boundaries() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    scores = await testsets.reviewer()
    print(scores)
    assert all(scores.values())
