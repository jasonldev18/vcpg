"""Timed mock interviews from the dossier alone, with a live scorecard (SPEC section 10)."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, Literal

from backend import db
from backend.errors import Conflict, NotFound
from backend.gate.rubric import quote_found
from backend.llm import client
from backend.orchestrator.context import tag, user_message
from backend.schemas import Scorecard

Focus = Literal["deep_dive", "system_design", "behavioral"]
Length = Literal[10, 20, 30]
TIME_UP = "Time is up. Thanks, that's the end of the interview."


def _now() -> datetime:
    return datetime.now(UTC)


def _row(conn: sqlite3.Connection, mock_id: int) -> sqlite3.Row:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM mock_interviews WHERE id = ?", (mock_id,)
    ).fetchone()
    if row is None:
        raise NotFound(f"Mock interview {mock_id} does not exist.")
    return row


def _dossier(conn: sqlite3.Connection, project_id: int) -> str:
    row = conn.execute(
        "SELECT markdown FROM dossiers WHERE project_id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise Conflict("Mock interviews unlock when the project is finished and archived.")
    return str(row["markdown"])


def seconds_left(row: sqlite3.Row) -> int:
    elapsed = _now() - datetime.fromisoformat(row["started_at"])
    return int(row["length_min"] * 60 - elapsed.total_seconds())


def _transcript(turns: list[dict[str, str]]) -> str:
    speaker = {"interviewer": "Interviewer", "learner": "Learner"}
    return "\n\n".join(f"{speaker[t['role']]}: {t['text']}" for t in turns) or "(not started)"


async def _ask(row: sqlite3.Row, dossier: str, turns: list[dict[str, str]], request: str) -> str:
    left = max(seconds_left(row), 0)
    message = user_message(
        tag("dossier", dossier),
        tag("focus", row["focus"]),
        tag("time", f"{left // 60} minutes {left % 60} seconds left of {row['length_min']}"),
        tag("conversation", _transcript(turns)),
        tag("request", request),
    )
    return await client.text("interviewer", message, project_id=row["project_id"], stream=True)


async def _score(row: sqlite3.Row, dossier: str, turns: list[dict[str, str]]) -> Scorecard:
    answers = [t["text"] for t in turns if t["role"] == "learner"]
    message = user_message(
        tag("dossier", dossier),
        tag("mock_answers", "\n\n".join(f"[{i + 1}] {a}" for i, a in enumerate(answers))),
        tag(
            "interviewer_questions",
            "\n\n".join(t["text"] for t in turns if t["role"] == "interviewer"),
        ),
    )
    card = await client.structured("grader", message, Scorecard, project_id=row["project_id"])
    for dim in card.dimensions:  # same rule as the gate: quotes must be the learner's words
        if dim.evidence and not quote_found(dim.evidence, answers):
            dim.evidence = None
    return card


def _save(
    conn: sqlite3.Connection,
    mock_id: int,
    turns: list[dict[str, str]],
    card: Scorecard | None,
    ended: bool,
) -> None:
    conn.execute(
        "UPDATE mock_interviews SET transcript = ?, scorecard_json = COALESCE(?, scorecard_json),"
        " ended_at = CASE WHEN ? THEN ? ELSE ended_at END WHERE id = ?",
        (
            json.dumps(turns),
            card.model_dump_json() if card else None,
            ended,
            _now().isoformat(),
            mock_id,
        ),
    )


async def start(project_id: int, length: Length, focus: Focus) -> int:
    with db.session() as conn:
        dossier = _dossier(conn, project_id)
        mock_id = conn.execute(
            "INSERT INTO mock_interviews (project_id, length_min, focus, started_at)"
            " VALUES (?, ?, ?, ?)",
            (project_id, length, focus, _now().isoformat()),
        ).lastrowid
        assert mock_id is not None
        row = _row(conn, mock_id)
    question = await _ask(row, dossier, [], "opening")
    with db.session() as conn:
        _save(conn, mock_id, [{"role": "interviewer", "text": question}], None, ended=False)
    return mock_id


async def answer(mock_id: int, text: str) -> None:
    with db.session() as conn:
        row = _row(conn, mock_id)
        if row["ended_at"]:
            raise Conflict("This interview has ended.")
        dossier = _dossier(conn, row["project_id"])
    turns = [*json.loads(row["transcript"]), {"role": "learner", "text": text}]
    card = await _score(row, dossier, turns)
    time_up = seconds_left(row) <= 0
    turns.append(
        {
            "role": "interviewer",
            "text": TIME_UP if time_up else await _ask(row, dossier, turns, "question"),
        }
    )
    with db.session() as conn:
        _save(conn, mock_id, turns, card, ended=time_up)


async def end(mock_id: int) -> None:
    """End and score: the scorecard with evidence and things to practise."""
    with db.session() as conn:
        row = _row(conn, mock_id)
        dossier = _dossier(conn, row["project_id"])
    turns = json.loads(row["transcript"])
    card = await _score(row, dossier, turns) if any(t["role"] == "learner" for t in turns) else None
    with db.session() as conn:
        _save(conn, mock_id, turns, card, ended=True)


def view(mock_id: int) -> dict[str, Any]:
    with db.session() as conn:
        row = _row(conn, mock_id)
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "length_min": row["length_min"],
        "focus": row["focus"],
        "seconds_left": max(seconds_left(row), 0) if not row["ended_at"] else 0,
        "ended": bool(row["ended_at"]),
        "transcript": json.loads(row["transcript"]),
        "scorecard": json.loads(row["scorecard_json"]) if row["scorecard_json"] else None,
    }
