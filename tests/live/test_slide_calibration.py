"""Live: on calibration/slides/, no slide makes a claim the step bundle does not support."""

import pytest

from backend import secrets
from backend.audit import testsets

pytestmark = pytest.mark.live


async def test_slides_only_claim_what_the_bundle_supports() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    scores = await testsets.slides()
    print(scores)
    assert all(scores.values())
