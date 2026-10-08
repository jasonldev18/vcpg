"""README coach and dossier: the last two stages of a project (SPEC sections 8 and 10)."""

import json
import re
import sqlite3
from typing import Any

from backend import db
from backend.errors import Conflict
from backend.llm import client
from backend.llm.client import LLMError
from backend.orchestrator import project_end, runner
from backend.orchestrator.context import tag, user_message
from backend.schemas import ReadmeReview
from backend.workspace import git

CODE_LIMIT = 50_000
DOSSIER_WORDS = 1_650  # "about 1,500"
NUMBER = re.compile(r"\d+(?:\.\d+)?")
LIST_MARKER = re.compile(r"(?m)^\s*(?:#+\s*)?\d+\.\s")
BLOCKING = {"does_not_match", "gap"}


def project_bundle(conn: sqlite3.Connection, project_id: int) -> str:
    """What the project is: plan, step summaries, test results, gate answers and code."""
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    plan = json.loads(project["plan_json"])
    lines = [
        f"Project: {project['name']}",
        f"One-liner: {plan['one_liner']}",
        f"Stack: {', '.join(plan['stack'])}",
    ]
    for step in conn.execute(
        "SELECT * FROM steps WHERE project_id = ? ORDER BY position", (project_id,)
    ).fetchall():
        answers = [a for a, _ in runner.graded_answers(conn, step["id"])]
        lines += [
            f"\nStep {step['position'] + 1}: {step['title']} ({step['goal']})",
            runner.build_summary(step),
            "Learner's gate answers:",
            *(f"- {a}" for a in answers),
        ]
    if project["final_review_json"]:
        final = json.loads(project["final_review_json"])
        lines += [
            "\nFinal test results:",
            *(f"- {c['cmd']}: {c['result']}, {c['summary']}" for c in final["commands"]),
        ]
    repo = runner._repo(conn, project_id)
    code, size = [], 0
    for path in git.tracked_files(repo):
        text = (repo / path).read_text(encoding="utf-8", errors="replace")
        if size + len(text) > CODE_LIMIT:
            code.append(f"--- {path} (not shown: size limit)")
            continue
        size += len(text)
        code.append(f"--- {path}\n{text}")
    return "\n".join(lines) + "\n\nCode:\n" + "\n".join(code)


def _readme(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM readmes WHERE project_id = ?", (project_id,)
    ).fetchone()
    return row


async def template(project_id: int) -> None:
    with db.session() as conn:
        project_end._stage(conn, project_id, "readme")
        if _readme(conn, project_id):
            return
        bundle = project_bundle(conn, project_id)
    text = await client.text(
        "readme_coach",
        user_message(tag("mode", "template"), tag("project", bundle)),
        project_id=project_id,
        stream=True,
    )
    with db.session() as conn:
        conn.execute(
            "INSERT INTO readmes (project_id, template, content) VALUES (?, ?, ?)",
            (project_id, text, text),
        )


def save(project_id: int, content: str) -> None:
    with db.session() as conn:
        project_end._stage(conn, project_id, "readme")
        if not _readme(conn, project_id):
            raise Conflict("The README template has not been written yet.")
        conn.execute(
            "UPDATE readmes SET content = ?, ready = 0 WHERE project_id = ?", (content, project_id)
        )


async def review(project_id: int) -> None:
    """Coach notes only; the README is ready when nothing blocks it (no mismatch, no gap)."""
    with db.session() as conn:
        project_end._stage(conn, project_id, "readme")
        row = _readme(conn, project_id)
        if row is None:
            raise Conflict("The README template has not been written yet.")
        numbered = "\n".join(
            f"{i}: {line}" for i, line in enumerate(row["content"].splitlines(), 1)
        )
        message = user_message(
            tag("mode", "review"),
            tag("project", project_bundle(conn, project_id)),
            tag("readme", numbered),
        )
    result = await client.structured("readme_coach", message, ReadmeReview, project_id=project_id)
    ready = not any(n.kind in BLOCKING for n in result.notes)
    with db.session() as conn:
        conn.execute(
            "UPDATE readmes SET review_json = ?, ready = ? WHERE project_id = ?",
            (result.model_dump_json(), ready, project_id),
        )


async def finish(project_id: int) -> None:
    """README ready: commit it to the workspace, write the dossier, and archive the project."""
    with db.session() as conn:
        project_end._stage(conn, project_id, "readme")
        row = _readme(conn, project_id)
        if row is None or not row["ready"]:
            raise Conflict("The coach has not passed the README yet.")
        repo = runner._repo(conn, project_id)
    (repo / "README.md").write_text(row["content"], encoding="utf-8")
    git.commit(repo, "README")
    await write_dossier(project_id)
    with db.session() as conn:
        project_end._advance_stage(conn, project_id, "done")


def dossier_problems(text: str, sources: str) -> list[str]:
    """Deterministic checks on the dossier: length, and no number the inputs do not contain."""
    problems = []
    if (words := len(text.split())) > DOSSIER_WORDS:
        problems.append(f"It is {words} words; keep it under about 1,500.")
    known = set(NUMBER.findall(sources))
    prose = LIST_MARKER.sub("", text)  # "1." numbering a list or heading is not a claim
    invented = sorted(set(NUMBER.findall(prose)) - known)
    if invented:
        problems.append(f"These numbers are not in the inputs: {', '.join(invented)}.")
    return problems


async def draft_dossier(blocks: list[str], project_id: int | None = None) -> str:
    """Write the dossier and check it in code; one retry with the problems, then give up."""
    sources = "\n".join(blocks)
    messages: list[dict[str, Any]] = user_message(*blocks)
    text = await client.text("dossier_writer", messages, project_id=project_id)
    if problems := dossier_problems(text, sources):
        fix = "Fix these problems and return the whole dossier:\n" + "\n".join(problems)
        messages += [{"role": "assistant", "content": text}, {"role": "user", "content": fix}]
        text = await client.text("dossier_writer", messages, project_id=project_id)
        if problems := dossier_problems(text, sources):
            raise LLMError("The dossier still breaks the rules: " + " ".join(problems))
    return text


async def write_dossier(project_id: int) -> None:
    with db.session() as conn:
        bundle = project_bundle(conn, project_id)
        slides = [r["json"] for r in conn.execute(
            "SELECT json FROM slides WHERE project_id = ? ORDER BY position", (project_id,)
        )]  # fmt: skip
        gates = [
            f"Step {s['title']}:\n"
            + "\n".join(
                f"- {a} -> {', '.join(i.status for i in g.items)}"
                for a, g in runner.graded_answers(conn, s["id"])
            )
            for s in conn.execute(
                "SELECT id, title FROM steps WHERE project_id = ? ORDER BY position", (project_id,)
            ).fetchall()
        ]
        readme = _readme(conn, project_id)
    blocks = [
        tag("project", bundle),
        tag("slides", "\n\n".join(slides)),
        tag("gates", "\n\n".join(gates)),
        tag("readme", readme["content"] if readme else ""),
    ]
    text = await draft_dossier(blocks, project_id)
    with db.session() as conn:
        conn.execute("DELETE FROM dossiers WHERE project_id = ?", (project_id,))
        conn.execute(
            "INSERT INTO dossiers (project_id, markdown) VALUES (?, ?)", (project_id, text)
        )


def view(project_id: int) -> dict[str, Any] | None:
    with db.session() as conn:
        row = _readme(conn, project_id)
    if row is None:
        return None
    return {
        "template": row["template"],
        "content": row["content"],
        "review": json.loads(row["review_json"]) if row["review_json"] else None,
        "ready": bool(row["ready"]),
    }
