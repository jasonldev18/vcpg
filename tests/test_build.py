"""Workspace creation, background builds, pause/stop, failures and the orchestrator's commit."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import TOKEN_HEADER, create_app
from backend.db import session
from backend.workspace import git
from tests.conftest import FakeBuilder, FakeLLM, wait_for


@pytest.fixture
def api() -> Iterator[TestClient]:
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as c:
        c.headers[TOKEN_HEADER] = c.get("/api/session").json()["token"]
        yield c


def approved(api: TestClient, fake_llm: FakeLLM) -> dict[str, Any]:
    fake_llm.reply_fixture("planner", "plan_recommender.json")
    pid = api.post("/api/projects", json={"brief": "x"}).json()["id"]
    return api.post(f"/api/projects/{pid}/plan/approve").json()


def step(api: TestClient, step_id: int) -> dict[str, Any]:
    return api.get(f"/api/steps/{step_id}").json()


def log(repo: Path) -> list[str]:
    out = subprocess.run(["git", "log", "--format=%s"], cwd=repo, capture_output=True, text=True)
    return out.stdout.split("\n")[:-1]


def test_approval_creates_a_git_workspace(api: TestClient, fake_llm: FakeLLM) -> None:
    project = approved(api, fake_llm)
    repo = git.workspace_path(project["id"])
    assert (repo / ".git").is_dir() and (repo / ".gitignore").exists()
    assert log(repo) == ["Start project"]


def test_build_writes_files_then_the_orchestrator_commits(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    project = approved(api, fake_llm)
    first = project["steps"][0]["id"]
    api.post(f"/api/steps/{first}/advance", json={"action": "ready"})
    wait_for(lambda: step(api, first)["state"] == "reviewed")

    repo = git.workspace_path(project["id"])
    [call] = fake_builder.calls
    assert call["agent"] == "builder" and call["cwd"] == repo and call["allow_install"] is True
    assert "<step>" in call["task"] and "Ratings loader" in call["task"]
    assert log(repo) == ["step 1: Ratings loader", "Start project"]
    with session() as conn:
        sha = conn.execute("SELECT commit_sha FROM steps WHERE id = ?", (first,)).fetchone()[0]
    assert sha == git.head(repo)
    assert f"step_{first}.py" in git.show(repo, sha)


def test_stop_keeps_files_and_returns_to_taught(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    project = approved(api, fake_llm)
    first = project["steps"][0]["id"]
    fake_builder.release.clear()
    view = api.post(f"/api/steps/{first}/advance", json={"action": "ready"}).json()
    assert view["state"] == "taught" and view["build"]["running"]

    wait_for(lambda: (git.workspace_path(project["id"]) / f"step_{first}.py").exists())
    view = api.post(f"/api/steps/{first}/advance", json={"action": "stop"}).json()
    wait_for(lambda: not step(api, first)["build"]["running"])
    after = step(api, first)
    assert after["state"] == "taught"
    assert (git.workspace_path(project["id"]) / f"step_{first}.py").exists()
    assert log(git.workspace_path(project["id"])) == ["Start project"]

    fake_builder.release.set()
    api.post(f"/api/steps/{first}/advance", json={"action": "build"})
    wait_for(lambda: step(api, first)["state"] == "reviewed")


def test_pause_and_resume_are_reported(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    first = approved(api, fake_llm)["steps"][0]["id"]
    fake_builder.release.clear()
    api.post(f"/api/steps/{first}/advance", json={"action": "ready"})
    paused = api.post(f"/api/steps/{first}/advance", json={"action": "pause"}).json()
    assert paused["build"] == {"running": True, "paused": True, "error": None}
    resumed = api.post(f"/api/steps/{first}/advance", json={"action": "resume"}).json()
    assert resumed["build"]["paused"] is False
    fake_builder.release.set()
    wait_for(lambda: step(api, first)["state"] == "reviewed")


def test_failed_build_shows_the_error_and_can_be_retried(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    first = approved(api, fake_llm)["steps"][0]["id"]
    fake_builder.fail = "The builder session failed: max_turns"
    api.post(f"/api/steps/{first}/advance", json={"action": "ready"})
    wait_for(lambda: step(api, first)["build"]["error"] is not None)
    assert step(api, first)["state"] == "taught"
    assert "max_turns" in step(api, first)["build"]["error"]

    fake_builder.fail = None
    api.post(f"/api/steps/{first}/advance", json={"action": "build"})
    wait_for(lambda: step(api, first)["state"] == "reviewed")
    assert step(api, first)["build"]["error"] is None


def test_controls_need_a_running_build(api: TestClient, fake_llm: FakeLLM) -> None:
    first = approved(api, fake_llm)["steps"][0]["id"]
    for action in ("stop", "pause", "build"):
        assert api.post(f"/api/steps/{first}/advance", json={"action": action}).status_code == 409


def test_retry_passes_the_previous_notes(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    first = approved(api, fake_llm)["steps"][0]["id"]
    with session() as conn:
        conn.execute(
            "UPDATE steps SET state = 'taught', build_note = ? WHERE id = ?",
            (json.dumps({"files": [], "decisions": ["old"], "not_done": ["tests"]}), first),
        )
    api.post(f"/api/steps/{first}/advance", json={"action": "build"})
    wait_for(lambda: step(api, first)["state"] == "reviewed")
    assert "<previous_notes>" in fake_builder.calls[0]["task"]
