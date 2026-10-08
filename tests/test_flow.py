"""Plan and step loop through the real routes, with recorded agent replies."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.schemas import Status
from tests.conftest import FakeLLM, wait_for

pytestmark = pytest.mark.usefixtures("fake_builder")

ANSWER = "I mean-centre each user's ratings so harsh and generous raters compare fairly."
QUOTE = "mean-centre each user's ratings"


def grade(*statuses: Status, evidence: str = QUOTE) -> str:
    items = [
        {
            "item_index": i,
            "status": s,
            "evidence": None if s == "missing" else evidence,
            "reason": "r",
        }
        for i, s in enumerate(statuses)
    ]
    return json.dumps({"items": items, "gap": "the cold-start case"})


def approved_project(api: TestClient, fake_llm: FakeLLM) -> dict[str, Any]:
    fake_llm.reply_fixture("planner", "plan_recommender.json")
    project = api.post("/api/projects", json={"brief": "recommend movies"}).json()
    return api.post(f"/api/projects/{project['id']}/plan/approve").json()


def build(api: TestClient, step_id: int) -> None:
    api.post(f"/api/steps/{step_id}/advance", json={"action": "ready"})
    wait_for(lambda: api.get(f"/api/steps/{step_id}").json()["state"] == "reviewed")


def at_gate(api: TestClient, fake_llm: FakeLLM) -> dict[str, Any]:
    """Approve, pass step 1 quickly, and open the gate on step 2 (four rubric items)."""
    project = approved_project(api, fake_llm)
    first, second = project["steps"][0]["id"], project["steps"][1]["id"]
    fake_llm.reply("interviewer", "Why is the matrix sparse?")
    build(api, first)
    api.post(f"/api/steps/{first}/advance", json={"action": "ready_for_interview"})
    fake_llm.reply("grader", grade("covered", "covered", "covered"))
    fake_llm.reply_fixture("slide_writer", "slide_step.json")
    api.post(f"/api/steps/{first}/gate/answer", json={"answer": ANSWER})
    fake_llm.reply("interviewer", "Why mean-centre?")
    build(api, second)
    return api.post(f"/api/steps/{second}/advance", json={"action": "ready_for_interview"}).json()


def test_brief_questions_answers_edit_approve(api: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.reply_fixture("planner", "plan_questions.json")
    project = api.post("/api/projects", json={"brief": "recommend movies"}).json()
    assert project["plan"]["questions"] == [
        "Where do the ratings come from?",
        "Who will use the recommendations?",
    ]
    pid = project["id"]
    assert api.post(f"/api/projects/{pid}/plan/approve").status_code == 409

    fake_llm.reply_fixture("planner", "plan_recommender.json")
    project = api.post(
        f"/api/projects/{pid}/plan/answers", json={"answers": ["MovieLens", "Just me"]}
    ).json()
    sent = fake_llm.requests_for("planner")[1][0]["content"]
    assert "Q: Where do the ratings come from?\nA: MovieLens" in sent
    assert project["name"] == "Movie Recommender"
    assert "rubric" not in json.dumps(project["plan"]).lower()

    edited = api.put(
        f"/api/projects/{pid}/plan",
        json={"steps": [{"source": 1, "title": "Recommender"}, {"source": 0, "title": "Loader"}]},
    ).json()
    assert [s["title"] for s in edited["plan"]["steps"]] == ["Recommender", "Loader"]

    project = api.post(f"/api/projects/{pid}/plan/approve").json()
    assert project["status"] == "active" and project["plan"] is None
    assert [(s["title"], s["progress"]["total"]) for s in project["steps"]] == [
        ("Recommender", 4),
        ("Loader", 3),
    ]
    assert project["current_step_id"] == project["steps"][0]["id"]


def test_plan_edit_rejects_duplicates_and_unknown_steps(api: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.reply_fixture("planner", "plan_recommender.json")
    pid = api.post("/api/projects", json={"brief": "x"}).json()["id"]
    for steps in (
        [{"source": 0, "title": "a"}, {"source": 0, "title": "b"}],
        [{"source": 7, "title": "a"}],
    ):
        assert api.put(f"/api/projects/{pid}/plan", json={"steps": steps}).status_code == 409


def test_revise_sends_the_current_plan_and_request(api: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.reply_fixture("planner", "plan_recommender.json")
    pid = api.post("/api/projects", json={"brief": "x"}).json()["id"]
    fake_llm.reply_fixture("planner", "plan_recommender.json")
    api.post(f"/api/projects/{pid}/plan/revise", json={"request": "add a web UI"})
    sent = fake_llm.requests_for("planner")[1][0]["content"]
    assert "<change_request>\nadd a web UI\n</change_request>" in sent
    assert "KNN recommender core" in sent


def test_later_steps_are_locked(api: TestClient, fake_llm: FakeLLM) -> None:
    project = approved_project(api, fake_llm)
    second = project["steps"][1]["id"]
    assert api.post(f"/api/steps/{second}/teach").status_code == 409
    assert api.post(f"/api/steps/{second}/advance", json={"action": "ready"}).status_code == 409


def test_teach_streams_once_and_is_kept(api: TestClient, fake_llm: FakeLLM) -> None:
    step_id = approved_project(api, fake_llm)["steps"][0]["id"]
    fake_llm.reply("tutor", "## What we are building\nA loader.")
    assert api.post(f"/api/steps/{step_id}/teach").json()["lesson"].startswith("## What")
    api.post(f"/api/steps/{step_id}/teach")
    assert len(fake_llm.requests_for("tutor")) == 1
    assert "<mode>\nteach\n</mode>" in fake_llm.requests_for("tutor")[0][0]["content"]


def test_side_chat_keeps_the_conversation(api: TestClient, fake_llm: FakeLLM) -> None:
    step_id = approved_project(api, fake_llm)["steps"][0]["id"]
    fake_llm.reply("tutor", "Sparse means mostly empty.")
    view = api.post(f"/api/steps/{step_id}/ask", json={"question": "What is sparse?"}).json()
    assert [(m["role"], m["content"]) for m in view["chat"]] == [
        ("user", "What is sparse?"),
        ("assistant", "Sparse means mostly empty."),
    ]


def test_build_then_interview_opens(api: TestClient, fake_llm: FakeLLM) -> None:
    step = at_gate(api, fake_llm)
    assert step["state"] == "interviewing"
    assert step["build_note"]["files"] == [{"path": f"step_{step['id']}.py", "summary": "adds x"}]
    assert step["gate"] == [
        {
            "id": step["gate"][0]["id"],
            "agent": "interviewer",
            "role": "assistant",
            "content": "Why mean-centre?",
        }
    ]
    assert step["progress"] == {"covered": 0, "total": 4}
    assert step["can_hint"] is False


def test_answer_updates_counts_only_and_asks_next(api: TestClient, fake_llm: FakeLLM) -> None:
    step_id = at_gate(api, fake_llm)["id"]
    fake_llm.reply("grader", grade("covered", "partial", "missing", "missing"))
    fake_llm.reply("interviewer", "What about a brand-new user?")
    view = api.post(f"/api/steps/{step_id}/gate/answer", json={"answer": ANSWER}).json()
    assert view["progress"] == {"covered": 1, "total": 4}
    assert view["gate"][-1]["content"] == "What about a brand-new user?"
    assert "mean-centring removes" not in json.dumps(view)  # rubric text never leaves the server
    assert "[covered]" in fake_llm.requests_for("interviewer")[-1][0]["content"]


def test_invented_evidence_does_not_count(api: TestClient, fake_llm: FakeLLM) -> None:
    step_id = at_gate(api, fake_llm)["id"]
    fake_llm.reply("grader", grade("covered", "covered", "covered", "covered", evidence="shard it"))
    fake_llm.reply("interviewer", "Try again?")
    view = api.post(f"/api/steps/{step_id}/gate/answer", json={"answer": ANSWER}).json()
    assert view["progress"]["covered"] == 0 and view["state"] == "interviewing"


def test_hint_ladder(api: TestClient, fake_llm: FakeLLM) -> None:
    step_id = at_gate(api, fake_llm)["id"]
    assert api.post(f"/api/steps/{step_id}/gate/hint").status_code == 409
    fake_llm.reply("grader", grade("missing", "missing", "missing", "missing"))
    fake_llm.reply("interviewer", "q")
    api.post(f"/api/steps/{step_id}/gate/answer", json={"answer": "no idea"})
    for _ in range(4):
        fake_llm.reply("interviewer", "hint")
        assert api.post(f"/api/steps/{step_id}/gate/hint").json()["can_hint"]
    requests = [r[0]["content"] for r in fake_llm.requests_for("interviewer")[-4:]]
    levels = [r.split("<request>\n")[1].split("\n")[0] for r in requests]
    assert levels == ["hint level 1", "hint level 2", "hint level 3", "hint level 3"]


def test_three_answers_without_progress_trigger_a_reteach(
    api: TestClient, fake_llm: FakeLLM
) -> None:
    step_id = at_gate(api, fake_llm)["id"]
    for _ in range(2):
        fake_llm.reply("grader", grade("missing", "missing", "missing", "missing"))
        fake_llm.reply("interviewer", "q")
        api.post(f"/api/steps/{step_id}/gate/answer", json={"answer": "dunno"})
    fake_llm.reply("grader", grade("missing", "missing", "missing", "missing"))
    fake_llm.reply("tutor", "Think of two film critics...")
    fake_llm.reply("interviewer", "Fresh question")
    view = api.post(f"/api/steps/{step_id}/gate/answer", json={"answer": "dunno"}).json()
    assert [m["role"] for m in view["gate"][-2:]] == ["reteach", "assistant"]
    reteach_request = fake_llm.requests_for("tutor")[-1][0]["content"]
    assert "<mode>\nreteach\n</mode>" in reteach_request and "cold-start" in reteach_request
    assert "<request>\nresume\n</request>" in fake_llm.requests_for("interviewer")[-1][0]["content"]


def test_teach_me_again_on_request(api: TestClient, fake_llm: FakeLLM) -> None:
    step_id = at_gate(api, fake_llm)["id"]
    fake_llm.reply("tutor", "Another angle")
    fake_llm.reply("interviewer", "q")
    view = api.post(f"/api/steps/{step_id}/gate/reteach").json()
    assert [m["content"] for m in view["gate"][-2:]] == ["Another angle", "q"]


def test_passing_the_gate_unlocks_the_next_step(api: TestClient, fake_llm: FakeLLM) -> None:
    step = at_gate(api, fake_llm)
    fake_llm.reply("grader", grade("covered", "covered", "partial", "missing"))
    fake_llm.reply("interviewer", "q")
    api.post(f"/api/steps/{step['id']}/gate/answer", json={"answer": ANSWER})
    fake_llm.reply("grader", grade("missing", "missing", "covered", "covered"))
    fake_llm.reply_fixture("slide_writer", "slide_step.json")
    view = api.post(f"/api/steps/{step['id']}/gate/answer", json={"answer": ANSWER}).json()
    assert view["state"] == "slide_done" and view["progress"] == {"covered": 4, "total": 4}
    sent = fake_llm.requests_for("slide_writer")[-1][0]["content"]
    assert "[2 of 4 points covered]" in sent and "[4 of 4 points covered]" in sent
    project = api.get(f"/api/projects/{step['project_id']}").json()
    assert project["current_step_id"] == project["steps"][2]["id"]


def test_missing_key_is_a_409_with_a_clear_message(api: TestClient, fake_llm: FakeLLM) -> None:
    step_id = approved_project(api, fake_llm)["steps"][0]["id"]
    fake_llm.replies.clear()
    from backend.llm import client

    client.transport = client._anthropic  # the real transport, with no key saved
    try:
        response = api.post(f"/api/steps/{step_id}/teach")
    finally:
        client.transport = fake_llm
    assert response.status_code == 409
    assert "Core access" in response.json()["detail"]


def test_a_failed_first_draft_leaves_no_half_made_project(
    api: TestClient, fake_llm: FakeLLM
) -> None:
    fake_llm.reply("planner", "not json")
    fake_llm.reply("planner", "still not json")
    assert api.post("/api/projects", json={"brief": "x"}).status_code == 502
    assert api.get("/api/projects/current").json() is None
