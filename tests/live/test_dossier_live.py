"""Live: the dossier stays under about 1,500 words and uses only numbers from its inputs."""

import pytest
import yaml

from backend import secrets
from backend.orchestrator.context import tag
from backend.orchestrator.wrapup import dossier_problems, draft_dossier
from backend.paths import REPO_ROOT

pytestmark = pytest.mark.live


async def test_dossier_is_short_and_only_uses_input_numbers() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    case = yaml.safe_load(
        (REPO_ROOT / "calibration" / "readme" / "knn_recommender.yaml").read_text(encoding="utf-8")
    )
    gates = (
        "Step KNN recommender core:\n- I subtract each user's mean so harsh and generous raters"
        " line up. -> covered, missing, missing, missing\nhints: 1"
    )
    blocks = [
        tag("project", case["project"]),
        tag("slides", "(none)"),
        tag("gates", gates),
        tag("readme", case["readme"]),
    ]
    text = await draft_dossier(blocks)
    print(f"\n{len(text.split())} words\n{text}")
    assert dossier_problems(text, "\n".join(blocks)) == []
    assert "I subtract each user's mean so harsh and generous raters line up." in text
