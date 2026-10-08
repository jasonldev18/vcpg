import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.db import connect
from backend.llm.config import AgentConfig, defaults, load, merge

AGENTS = {
    "planner", "tutor", "builder", "reviewer", "interviewer", "grader", "slide_writer",
    "rook", "bolt", "echo", "pixel",
    "lesson_builder", "idea_generator", "readme_coach", "dossier_writer",
}  # fmt: skip


def test_yaml_defines_every_agent() -> None:
    cfgs = defaults()
    assert set(cfgs) == AGENTS
    assert cfgs["planner"] == AgentConfig(
        model="claude-opus-5-5", effort="high", runtime="api", max_tokens=16000
    )
    assert cfgs["builder"].max_turns == 60


def test_override_of_effort_low_is_rejected() -> None:
    with pytest.raises(ValidationError):
        merge(defaults()["tutor"], {"effort": "low"})


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(ValidationError):
        merge(defaults()["tutor"], {"model": "gpt-5"})


def test_load_applies_override_row_and_keeps_limits() -> None:
    conn = connect()
    conn.execute("INSERT INTO agent_overrides VALUES ('grader', 'claude-sonnet-5-5', 'xhigh')")
    cfg = load("grader", conn)
    assert (cfg.model, cfg.effort, cfg.max_tokens) == ("claude-sonnet-5-5", "xhigh", 4000)
    assert load("tutor", conn) == defaults()["tutor"]


def test_runtime_limit_mismatch_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(model="claude-opus-5-5", effort="high", runtime="agent_sdk", max_tokens=10)


def test_squad_lists_every_agent_and_saves_only_real_overrides(api: TestClient) -> None:
    squad = {a["agent"]: a for a in api.get("/api/squad").json()}
    assert set(squad) == AGENTS
    assert squad["builder"]["group"] == "build_crew" and squad["builder"]["runtime"] == "agent_sdk"
    assert squad["rook"]["group"] == "audit_crew" and squad["lesson_builder"]["group"] == "helpers"

    saved = api.put(
        "/api/squad",
        json={
            "agents": [
                {"agent": "tutor", "model": "claude-opus-5-5", "effort": "max"},
                {"agent": "planner", "model": "claude-opus-5-5", "effort": "high"},  # = default
            ]
        },
    ).json()
    by_name = {a["agent"]: a for a in saved}
    assert by_name["tutor"]["custom"] and by_name["tutor"]["effort"] == "max"
    assert not by_name["planner"]["custom"]

    low = {"agents": [{"agent": "tutor", "model": "claude-opus-5-5", "effort": "low"}]}
    assert api.put("/api/squad", json=low).status_code == 422
    unknown = {"agents": [{"agent": "nobody", "model": "claude-opus-5-5", "effort": "high"}]}
    assert api.put("/api/squad", json=unknown).status_code == 404

    reset = {"agents": [{"agent": "tutor", "model": "claude-sonnet-5-5", "effort": "high"}]}
    assert not {a["agent"]: a for a in api.put("/api/squad", json=reset).json()}["tutor"]["custom"]
