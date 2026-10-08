import pytest
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
