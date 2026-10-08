"""Squad loadout: every agent's model and effort; overrides go to the database (SPEC 11)."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend import db
from backend.errors import NotFound
from backend.llm.config import Effort, Model, defaults, groups, load, merge

router = APIRouter(prefix="/api/squad")


class Loadout(BaseModel):
    agent: str
    model: Model
    effort: Effort  # medium, high, xhigh or max: never low


class Save(BaseModel):
    agents: list[Loadout]


def squad() -> list[dict[str, Any]]:
    with db.session() as conn:
        return [
            {
                "agent": name,
                "group": groups()[name],
                "runtime": base.runtime,
                "model": (cfg := load(name, conn)).model,
                "effort": cfg.effort,
                "recommended": {"model": base.model, "effort": base.effort},
                "custom": (cfg.model, cfg.effort) != (base.model, base.effort),
            }
            for name, base in defaults().items()
        ]


@router.get("")
def get() -> list[dict[str, Any]]:
    return squad()


@router.put("")
def save(body: Save) -> list[dict[str, Any]]:
    """Choices equal to the recommended loadout are stored as no override at all."""
    with db.session() as conn:
        for choice in body.agents:
            if choice.agent not in defaults():
                raise NotFound(f"There is no agent called {choice.agent}.")
            base = defaults()[choice.agent]
            merge(base, {"model": choice.model, "effort": choice.effort})  # validates the pair
            conn.execute("DELETE FROM agent_overrides WHERE agent = ?", (choice.agent,))
            if (choice.model, choice.effort) != (base.model, base.effort):
                conn.execute(
                    "INSERT INTO agent_overrides (agent, model, effort) VALUES (?, ?, ?)",
                    (choice.agent, choice.model, choice.effort),
                )
    return squad()
