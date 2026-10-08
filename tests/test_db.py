import sqlite3
from pathlib import Path

import pytest

from backend.db import connect, migrate

TABLES = {
    "projects", "steps", "rubric_items", "attempts", "messages", "slides", "deck_exports",
    "readmes", "lessons", "sources", "passages", "dossiers", "mock_interviews", "agent_calls",
    "agent_overrides", "audit_runs", "audit_issues", "audit_prs",
}  # fmt: skip


def test_connect_creates_every_table_under_vcpg_home(isolated_home: Path) -> None:
    conn = connect()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert (isolated_home / "vcpg.db").exists()
    assert tables == TABLES
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_migrate_twice_keeps_data() -> None:
    conn = connect()
    conn.execute("INSERT INTO agent_overrides VALUES ('tutor', 'claude-opus-5-5', 'max')")
    conn.commit()
    migrate(conn)
    assert conn.execute("SELECT COUNT(*) FROM agent_overrides").fetchone()[0] == 1


def test_schema_rejects_low_effort_override() -> None:
    conn = connect()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO agent_overrides VALUES ('tutor', 'claude-opus-5-5', 'low')")
