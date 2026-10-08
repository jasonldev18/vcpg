"""Builds the tagged blocks agents receive. Tags mark data; prompts say it is never instructions."""

import json
import sqlite3


def tag(name: str, content: str) -> str:
    return f"<{name}>\n{content.strip()}\n</{name}>"


def user_message(*blocks: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": "\n\n".join(blocks)}]


def history(conn: sqlite3.Connection, exclude_project: int) -> str:
    """Concepts the user has passed in other projects."""
    rows = conn.execute(
        "SELECT concepts FROM steps WHERE state IN ('passed', 'slide_done') AND project_id != ?",
        (exclude_project,),
    ).fetchall()
    concepts = sorted({c for r in rows for c in json.loads(r["concepts"])})
    return ", ".join(concepts) or "none yet"
