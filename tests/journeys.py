"""Shared journeys through the API with recorded agent replies."""

import json
from typing import Any

from fastapi.testclient import TestClient

from backend.schemas import Status
from tests.conftest import FakeLLM, wait_for

ANSWER = "Each user's ratings are loaded into a sparse matrix because most films are unrated."
QUOTE = "most films are unrated"


def grade(*statuses: Status) -> str:
    items = [
        {"item_index": i, "status": s, "evidence": None if s == "missing" else QUOTE, "reason": "r"}
        for i, s in enumerate(statuses)
    ]
    return json.dumps({"items": items, "gap": "g"})


def project(api: TestClient, pid: int) -> dict[str, Any]:
    return api.get(f"/api/projects/{pid}").json()


def finished_steps(api: TestClient, fake_llm: FakeLLM) -> int:
    """A one-step project taken through build, tour and a two-answer gate."""
    fake_llm.reply_fixture("planner", "plan_one_step.json")
    pid = api.post("/api/projects", json={"brief": "x"}).json()["id"]
    step_id = api.post(f"/api/projects/{pid}/plan/approve").json()["steps"][0]["id"]
    api.post(f"/api/steps/{step_id}/advance", json={"action": "ready"})
    wait_for(lambda: api.get(f"/api/steps/{step_id}").json()["state"] == "reviewed")
    fake_llm.reply("interviewer", "Why a sparse matrix?")
    api.post(f"/api/steps/{step_id}/advance", json={"action": "ready_for_interview"})
    fake_llm.reply("grader", grade("covered", "missing", "missing"))
    fake_llm.reply("interviewer", "And missing ratings?")
    api.post(f"/api/steps/{step_id}/gate/answer", json={"answer": ANSWER})
    fake_llm.reply("grader", grade("covered", "covered", "covered"))
    fake_llm.reply_fixture("slide_writer", "slide_code.json")
    api.post(f"/api/steps/{step_id}/gate/answer", json={"answer": ANSWER})
    return pid


def finished_deck(api: TestClient, fake_llm: FakeLLM) -> tuple[int, list[Any]]:
    pid = finished_steps(api, fake_llm)
    api.post(f"/api/projects/{pid}/final-review")
    wait_for(lambda: project(api, pid)["finish"]["stage"] == "retest")
    fake_llm.reply("interviewer", "q")
    api.post(f"/api/projects/{pid}/retest/start")
    fake_llm.reply("grader", grade("covered"))
    for kind in ("title", "overview", "retro"):
        fake_llm.reply_fixture("slide_writer", f"slide_{kind}.json")
    api.post(f"/api/projects/{pid}/retest/answer", json={"answer": ANSWER})
    return pid, api.get(f"/api/projects/{pid}/deck").json()["slides"]
