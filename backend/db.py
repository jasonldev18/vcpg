import sqlite3
from pathlib import Path

from backend.paths import vcpg_home

MIGRATIONS = Path(__file__).parent / "migrations"


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or vcpg_home() / "vcpg.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply numbered SQL files above the stored user_version, each in one transaction."""
    current: int = conn.execute("PRAGMA user_version").fetchone()[0]
    for file in sorted(MIGRATIONS.glob("*.sql")):
        number = int(file.name.split("_", 1)[0])
        if number > current:
            sql = file.read_text(encoding="utf-8")
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
