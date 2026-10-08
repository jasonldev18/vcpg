"""Review loop (retry once, then blocked), Edit plan, and the code tour."""

import json
from typing import Any

from fastapi.testclient import TestClient

from backend.workspace import git
from tests.conftest import FIXTURES, FakeBuilder, FakeLLM, wait_for


def approved(api: TestClient, fake_llm: FakeLLM) -> dict[str, Any]:
    fake_llm.reply_fixture("planner", "plan_recommender.json")
    pid = api.post("/api/projects", json={"brief": "x"}).json()["id"]
    return api.post(f"/api/projects/{pid}/plan/approve").json()


def step(api: TestClient, step_id: int) -> dict[str, Any]:
    return api.get(f"/api/steps/{step_id}").json()


def build(api: TestClient, step_id: int, until: str) -> dict[str, Any]:
    api.post(f"/api/steps/{step_id}/advance", json={"action": "ready"})
    wait_for(lambda: step(api, step_id)["state"] == until)
    return step(api, step_id)


def test_reviewer_gets_the_diff_and_its_note_is_kept(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    first = approved(api, fake_llm)["steps"][0]["id"]
    view = build(api, first, "reviewed")
    assert fake_builder.agents() == ["builder", "reviewer"]
    review_call = fake_builder.calls[1]
    assert review_call["allow_install"] is False
    assert f"step_{first}.py" in review_call["task"] and "<diff>" in review_call["task"]
    assert view["review_note"]["status"] == "pass"
    assert view["review_note"]["cut"][0]["why"] == "nothing uses it"


def test_a_failed_review_sends_the_step_back_to_the_builder_once(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    project = approved(api, fake_llm)
    first = project["steps"][0]["id"]
    fake_builder.reviews.extend(["fail", "pass"])
    build(api, first, "reviewed")
    assert fake_builder.agents() == ["builder", "reviewer", "builder", "reviewer"]
    retry_task = fake_builder.calls[2]["task"]
    assert "<previous_notes>" in retry_task and "off by one" in retry_task
    log = git.show(git.workspace_path(project["id"]), "HEAD")
    assert "step 1: Ratings loader" in log


def test_two_failed_reviews_block_the_step_without_committing(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    project = approved(api, fake_llm)
    first = project["steps"][0]["id"]
    fake_builder.reviews.extend(["fail", "fail"])
    view = build(api, first, "blocked")
    assert view["build_note"] and view["review_note"]["failure"] == "test_x fails: off by one"
    assert "Start project" in git.show(git.workspace_path(project["id"]), "HEAD")

    api.post(f"/api/steps/{first}/advance", json={"action": "retry"})
    wait_for(lambda: step(api, first)["state"] == "reviewed")


def test_edit_plan_replaces_only_unpassed_steps_after_approval(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    project = approved(api, fake_llm)
    pid, first = project["id"], project["steps"][0]["id"]
    fake_builder.reviews.extend(["fail", "fail"])
    build(api, first, "blocked")

    revised = json.loads((FIXTURES / "plan_recommender.json").read_text())
    revised["steps"] = revised["steps"][1:]
    fake_llm.reply("planner", json.dumps(revised))
    view = api.post(f"/api/projects/{pid}/replan", json={"request": "drop the loader"}).json()
    sent = fake_llm.requests_for("planner")[-1][0]["content"]
    assert "<passed_steps>\nnone\n</passed_steps>" in sent and "is blocked" in sent
    assert [s["title"] for s in view["replan"]["old"]] == [
        "Ratings loader",
        "KNN recommender core",
        "Offline evaluation",
    ]
    assert [s["title"] for s in view["replan"]["new"]] == [
        "KNN recommender core",
        "Offline evaluation",
    ]
    assert "rubric" not in json.dumps(view["replan"]).lower()

    view = api.post(f"/api/projects/{pid}/replan/approve").json()
    assert view["replan"] is None
    assert [s["title"] for s in view["steps"]] == ["KNN recommender core", "Offline evaluation"]
    assert view["steps"][0]["progress"]["total"] == 4


def test_discarding_a_revision_keeps_the_plan(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    project = approved(api, fake_llm)
    fake_llm.reply_fixture("planner", "plan_recommender.json")
    api.post(f"/api/projects/{project['id']}/replan", json={"request": "x"})
    view = api.delete(f"/api/projects/{project['id']}/replan").json()
    assert view["replan"] is None and len(view["steps"]) == 3


def test_tour_reads_the_commit_and_serves_only_toured_files(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    first = approved(api, fake_llm)["steps"][0]["id"]
    build(api, first, "reviewed")
    stop = {"file": f"step_{first}.py", "line_start": 1, "line_end": 1, "explanation": "x"}
    fake_llm.reply("tutor", json.dumps({"stops": [stop]}))
    view = api.post(f"/api/steps/{first}/tour").json()
    assert view["tour"]["stops"] == [stop]
    sent = fake_llm.requests_for("tutor")[-1][0]["content"]
    assert "<mode>\ntour\n</mode>" in sent and f"step_{first}.py" in sent and "+x = 1" in sent

    code = api.get(f"/api/steps/{first}/file", params={"path": f"step_{first}.py"}).json()
    assert code["lines"] == ["x = 1"]
    assert api.get(f"/api/steps/{first}/file", params={"path": ".gitignore"}).status_code == 404

    api.post(f"/api/steps/{first}/tour")
    assert len(fake_llm.requests_for("tutor")) == 1  # generated once


def test_interviewer_sees_notes_and_tour_lines(
    api: TestClient, fake_llm: FakeLLM, fake_builder: FakeBuilder
) -> None:
    first = approved(api, fake_llm)["steps"][0]["id"]
    build(api, first, "reviewed")
    stop = {"file": "app.py", "line_start": 3, "line_end": 9, "explanation": "x"}
    fake_llm.reply("tutor", json.dumps({"stops": [stop]}))
    api.post(f"/api/steps/{first}/tour")
    fake_llm.reply("interviewer", "Why?")
    api.post(f"/api/steps/{first}/advance", json={"action": "ready_for_interview"})
    sent = fake_llm.requests_for("interviewer")[-1][0]["content"]
    assert "Code at app.py:3-9" in sent and "Reviewer cut from app.py" in sent
