"""Agent model settings: config/agents.yaml defaults merged with Squad overrides."""

import sqlite3
from collections.abc import Mapping
from functools import cache
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from backend.paths import REPO_ROOT

Model = Literal["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
Effort = Literal["medium", "high", "xhigh", "max"]  # never below medium


class AgentConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: Model
    effort: Effort
    runtime: Literal["api", "agent_sdk"]
    max_tokens: int | None = None
    max_turns: int | None = None

    @model_validator(mode="after")
    def limit_matches_runtime(self) -> Self:
        if (self.runtime == "api") != (self.max_tokens is not None and self.max_turns is None):
            raise ValueError(
                "api agents need max_tokens only; agent_sdk agents need max_turns only"
            )
        return self


@cache
def defaults() -> dict[str, AgentConfig]:
    groups = yaml.safe_load((REPO_ROOT / "config" / "agents.yaml").read_text(encoding="utf-8"))
    return {
        name: AgentConfig.model_validate(cfg)
        for agents in groups.values()
        for name, cfg in agents.items()
    }


def merge(base: AgentConfig, override: Mapping[str, str]) -> AgentConfig:
    return AgentConfig.model_validate(base.model_dump() | dict(override))


def load(agent: str, conn: sqlite3.Connection) -> AgentConfig:
    row = conn.execute(
        "SELECT model, effort FROM agent_overrides WHERE agent = ?", (agent,)
    ).fetchone()
    base = defaults()[agent]
    return merge(base, dict(row)) if row else base


@cache
def groups() -> dict[str, str]:
    """Which crew each agent belongs to, as config/agents.yaml groups them."""
    raw = yaml.safe_load((REPO_ROOT / "config" / "agents.yaml").read_text(encoding="utf-8"))
    return {name: group for group, agents in raw.items() for name in agents}
