"""Live: the real grader, through the real gate pipeline, agrees with calibration/gate/."""

import pytest

from backend import secrets
from backend.audit import testsets

pytestmark = pytest.mark.live


async def test_grader_agrees_with_calibration_set() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    scores = await testsets.gate()
    print(
        "\n"
        + "\n".join(f"{'ok ' if v else 'MISS'} {k}" for k, v in sorted(scores.items()) if not v)
    )
    agreement = sum(scores.values()) / len(scores)
    print(f"agreement: {sum(scores.values()):.0f}/{len(scores)} = {agreement:.0%}")
    assert agreement >= 0.9
