"""Give me ideas: four project cards for a topic (SPEC 3.2)."""

import json
import sqlite3
from typing import Any

from backend import db
from backend.errors import NotFound
from backend.lessons import builder
from backend.llm import client
from backend.orchestrator import planning
from backend.orchestrator.context import tag, user_message
from backend.schemas import IdeaBatch, IdeaCard


def _passed_concepts(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT concepts FROM steps WHERE state IN ('passed', 'slide_done')"
    ).fetchall()
    return {c.lower() for r in rows for c in json.loads(r["concepts"])}


def _familiarity(card: IdeaCard, used: set[str], basics: set[str]) -> IdeaCard:
    """From the learner's history, never the model's guess."""
    concepts = [
        c.model_copy(
            update={
                "familiarity": "used"
                if c.name.lower() in used
                else "basics"
                if c.name.lower() in basics
                else "new"
            }
        )
        for c in card.concepts
    ]
    return card.model_copy(update={"concepts": concepts})


async def generate(topic: str, use: str, data: str) -> int:
    with db.session() as conn:
        used = _passed_concepts(conn)
    message = user_message(
        tag("topic", topic),
        tag("use", use),
        tag("data", data),
        tag("history", ", ".join(sorted(used)) or "none yet"),
    )
    batch = await client.structured("idea_generator", message, IdeaBatch)
    basics = builder.studied_concepts()
    cards = [_familiarity(c, used, basics).model_dump() for c in batch.cards]
    with db.session() as conn:
        idea_id = conn.execute(
            "INSERT INTO ideas (topic, cards_json) VALUES (?, ?)", (topic, json.dumps(cards))
        ).lastrowid
    assert idea_id is not None
    return idea_id


def card(idea_id: int, index: int) -> IdeaCard:
    with db.session() as conn:
        row = conn.execute("SELECT cards_json FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    cards = json.loads(row["cards_json"]) if row else []
    if not 0 <= index < len(cards):
        raise NotFound("That idea does not exist.")
    return IdeaCard.model_validate(cards[index])


def brief(c: IdeaCard) -> str:
    return (
        f"{c.name}: {c.line}\n\n{c.pitch}\n\nArchitecture: {' -> '.join(c.architecture)}\n"
        f"Concepts: {', '.join(x.name for x in c.concepts)}\n"
        f"Questions I want to be able to answer:\n" + "\n".join(f"- {q}" for q in c.questions)
    )


async def build(idea_id: int, index: int) -> int:
    """Build this: the card becomes the planner's brief."""
    return await planning.create(brief(card(idea_id, index)), start_path="idea")


async def teach_first(idea_id: int, index: int) -> int:
    """Teach me first: a lesson path for the card's new concepts, returning to the card."""
    c = card(idea_id, index)
    new = [x.name for x in c.concepts if x.familiarity == "new"] or [x.name for x in c.concepts]
    return await builder.create_path(", ".join(new), return_idea=idea_id, return_card=index)


def view(idea_id: int) -> dict[str, Any]:
    with db.session() as conn:
        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    if row is None:
        raise NotFound(f"Ideas {idea_id} do not exist.")
    return {"id": row["id"], "topic": row["topic"], "cards": json.loads(row["cards_json"])}
