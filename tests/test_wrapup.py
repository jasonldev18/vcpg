"""README coach, dossier, archive and timed mock interviews."""

import json
import subprocess
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.orchestrator import mock, wrapup
from backend.workspace import git
from tests.conftest import FakeBuilder, FakeLLM
from tests.journeys import project

README = "# Movie Recommender\nUses cosine similarity with k = 20.\n## How to run\npytest -q\n"


def note(kind: str, line: int = 2) -> dict[str, Any]:
    return {"line": line, "kind": kind, "note": "n", "project_shows": "recommend.py uses cosine"}


@pytest.fixture
def at_readme(api: TestClient, fake_llm: FakeLLM, deck: tuple[int, list[Any]]) -> int:
    pid, _ = deck
    api.post(f"/api/projects/{pid}/deck/done")
    fake_llm.reply("readme_coach", "# Title\n<!-- Write one line on what it does. -->\n")
    api.post(f"/api/projects/{pid}/readme/template")
    return pid


def test_template_then_review_until_ready(
    api: TestClient,
    fake_llm: FakeLLM,
    at_readme: int,
) -> None:
    pid = at_readme
    view = api.get(f"/api/projects/{pid}/readme").json()
    assert view["content"].startswith("# Title") and view["ready"] is False
    assert "<mode>\ntemplate\n</mode>" in fake_llm.requests_for("readme_coach")[0][0]["content"]

    api.put(f"/api/projects/{pid}/readme", json={"content": README})
    fake_llm.reply("readme_coach", json.dumps({"notes": [note("does_not_match"), note("unclear")]}))
    view = api.post(f"/api/projects/{pid}/readme/review").json()
    assert view["ready"] is False and view["review"]["notes"][0]["kind"] == "does_not_match"
    sent = fake_llm.requests_for("readme_coach")[-1][0]["content"]
    assert "2: Uses cosine similarity with k = 20." in sent and "--- step_" in sent

    fake_llm.reply("readme_coach", json.dumps({"notes": [note("unclear")]}))
    assert api.post(f"/api/projects/{pid}/readme/review").json()["ready"] is True
    api.put(f"/api/projects/{pid}/readme", json={"content": README + "edit\n"})
    assert (
        api.get(f"/api/projects/{pid}/readme").json()["ready"] is False
    )  # edits need a new review


def test_finish_commits_readme_writes_dossier_and_archives(
    api: TestClient,
    fake_llm: FakeLLM,
    at_readme: int,
) -> None:
    pid = at_readme
    assert api.post(f"/api/projects/{pid}/readme/finish").status_code == 409
    api.put(f"/api/projects/{pid}/readme", json={"content": README})
    fake_llm.reply("readme_coach", json.dumps({"notes": []}))
    api.post(f"/api/projects/{pid}/readme/review")

    fake_llm.reply("dossier_writer", "## Results\nPrecision rose to 97%.")
    fake_llm.reply("dossier_writer", "## Results\nNo results were measured.")
    api.post(f"/api/projects/{pid}/readme/finish")
    retry = fake_llm.requests_for("dossier_writer")[1][-1]["content"]
    assert "97" in retry and "not in the inputs" in retry

    repo = git.workspace_path(pid)
    assert (repo / "README.md").read_text() == README
    log = subprocess.run(["git", "log", "--format=%s"], cwd=repo, capture_output=True, text=True)
    assert log.stdout.split("\n")[0] == "README"
    assert project(api, pid)["status"] == "done"
    [entry] = api.get("/api/archive").json()
    assert entry["dossier"].endswith("No results were measured.") and entry["readme"] == README


def test_dossier_checks_length_and_numbers() -> None:
    sources = "k = 20, 610 users, 4 passed"
    assert wrapup.dossier_problems("## 1. Mission\n1. Uses k = 20 for 610 users.", sources) == []
    [problem] = wrapup.dossier_problems("Precision was 0.42.", sources)
    assert "0.42" in problem
    assert "words" in wrapup.dossier_problems("word " * 2000, sources)[0]


@pytest.fixture
def archived(api: TestClient, fake_llm: FakeLLM, at_readme: int) -> int:
    pid = at_readme
    api.put(f"/api/projects/{pid}/readme", json={"content": README})
    fake_llm.reply("readme_coach", json.dumps({"notes": []}))
    api.post(f"/api/projects/{pid}/readme/review")
    fake_llm.reply("dossier_writer", "## Mission\nRecommends films with cosine similarity.")
    api.post(f"/api/projects/{pid}/readme/finish")
    return pid


def card(evidence: str) -> str:
    dims = ["system_design", "failure_modes", "motivation_and_impact", "communication"]
    return json.dumps(
        {
            "dimensions": [
                {
                    "name": d,
                    "score": 3,
                    "evidence": evidence if i == 0 else "words never said",
                    "reason": "r",
                }
                for i, d in enumerate(dims)
            ],
            "practise": ["explain k"],
        }
    )


def test_mock_interview_uses_only_the_dossier_and_verifies_quotes(
    api: TestClient, fake_llm: FakeLLM, archived: int
) -> None:
    fake_llm.reply("interviewer", "Hi. Walk me through the recommender.")
    view = api.post(
        f"/api/archive/{archived}/mock", json={"length_min": 10, "focus": "deep_dive"}
    ).json()
    assert view["seconds_left"] > 590 and view["transcript"][0]["role"] == "interviewer"
    opening = fake_llm.requests_for("interviewer")[-1][0]["content"]
    assert "<dossier>\n## Mission" in opening and "<focus>\ndeep_dive\n</focus>" in opening
    assert "<step>" not in opening and "step_" not in opening  # dossier only, no code

    fake_llm.reply("grader", card("cosine compares direction"))
    fake_llm.reply("interviewer", "Why direction?")
    answer = "I used cosine; cosine compares direction, not size."
    view = api.post(f"/api/mock/{view['id']}/answer", json={"answer": answer}).json()
    dims = view["scorecard"]["dimensions"]
    assert dims[0]["evidence"] == "cosine compares direction"
    assert all(d["evidence"] is None for d in dims[1:])  # invented quotes are dropped
    assert [t["role"] for t in view["transcript"]] == ["interviewer", "learner", "interviewer"]

    fake_llm.reply("grader", card("cosine compares direction"))
    ended = api.post(f"/api/mock/{view['id']}/end").json()
    assert ended["ended"] and ended["scorecard"]["practise"] == ["explain k"]
    assert api.post(f"/api/mock/{view['id']}/answer", json={"answer": "x"}).status_code == 409


def test_mock_stops_asking_when_time_is_up(
    api: TestClient, fake_llm: FakeLLM, archived: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm.reply("interviewer", "First question?")
    mock_id = api.post(
        f"/api/archive/{archived}/mock", json={"length_min": 10, "focus": "behavioral"}
    ).json()["id"]
    later = mock._now() + timedelta(minutes=11)
    monkeypatch.setattr(mock, "_now", lambda: later)
    asked = len(fake_llm.requests_for("interviewer"))
    fake_llm.reply("grader", card("x"))
    view = api.post(f"/api/mock/{mock_id}/answer", json={"answer": "x"}).json()
    assert view["ended"] and view["transcript"][-1]["text"] == mock.TIME_UP
    assert len(fake_llm.requests_for("interviewer")) == asked  # no question after time ran out


def test_mock_needs_a_finished_project(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    fake_llm.reply_fixture("planner", "plan_one_step.json")
    pid = api.post("/api/projects", json={"brief": "x"}).json()["id"]
    assert (
        api.post(
            f"/api/archive/{pid}/mock", json={"length_min": 10, "focus": "behavioral"}
        ).status_code
        == 409
    )
