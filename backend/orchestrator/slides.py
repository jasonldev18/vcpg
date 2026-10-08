"""Interview slides: one per step, plus title, overview and retrospective (SPEC 5.6 and 7)."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

from backend import db
from backend.errors import Conflict, NotFound
from backend.exports import pdf, pptx
from backend.gate import rubric
from backend.llm import client
from backend.orchestrator import runner
from backend.orchestrator.context import tag, user_message
from backend.paths import vcpg_home
from backend.schemas import Slide
from backend.workspace import git

Kind = Literal["title", "overview", "step", "retrospective"]
ORDER: dict[str, int] = {"title": 0, "overview": 1, "step": 2, "retrospective": 3}


def _gate_transcript(conn: sqlite3.Connection, step_id: int) -> str:
    """The interview with progress after each answer and every hint, for 'struggled'."""
    texts = [r["text"] for r in runner._items(conn, step_id)]
    states = iter(rubric.replay(texts, runner.graded_answers(conn, step_id)))
    lines = []
    for m in runner._messages(conn, step_id, runner.GATE):
        if m["role"] == "user":
            covered = rubric.progress(next(states))["covered"]
            lines.append(f"Learner: {m['content']}  [{covered} of {len(texts)} points covered]")
        else:
            speaker = "Tutor (re-teach)" if m["role"] == "reteach" else "Interviewer"
            lines.append(f"{speaker}: {m['content']}")
    hints = sum(a["kind"] == "hint" for a in runner._attempts(conn, step_id))
    lines.append(f"[hints given in total: {hints}]")
    return "\n\n".join(lines)


def _code_files(conn: sqlite3.Connection, step: sqlite3.Row) -> str:
    if not step["commit_sha"]:
        return "(no commit)"
    repo = runner._repo(conn, step["project_id"])
    files = git.changed_files(repo, step["commit_sha"])
    return "\n".join(
        f"{f}: {len(git.file_at(repo, step['commit_sha'], f).splitlines())} lines" for f in files
    )


def _step_message(conn: sqlite3.Connection, step: sqlite3.Row, instruction: str | None) -> str:
    blocks = [
        tag("mode", "step"),
        runner._step_block(step),
        tag("build_summary", runner.build_summary(step)),
        tag("build_note", step["build_note"] or ""),
        tag("review_note", step["review_note"] or ""),
        tag("code_files", _code_files(conn, step)),
        tag("gate", _gate_transcript(conn, step["id"])),
    ]
    return "\n\n".join([*blocks, *([tag("instruction", instruction)] if instruction else [])])


def _project_message(
    conn: sqlite3.Connection, project_id: int, kind: Kind, instruction: str | None
) -> str:
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    plan = json.loads(project["plan_json"])
    steps = [r["title"] for r in conn.execute(
        "SELECT title FROM steps WHERE project_id = ? ORDER BY position", (project_id,)
    )]  # fmt: skip
    slides = [r["json"] for r in conn.execute(
        "SELECT json FROM slides WHERE project_id = ? AND kind = 'step' ORDER BY position",
        (project_id,),
    )]  # fmt: skip
    blocks = [
        tag("mode", kind),
        tag(
            "plan",
            f"Project: {project['name']}\nOne-liner: {plan['one_liner']}\n"
            f"Stack: {', '.join(plan['stack'])}\nSteps:\n" + "\n".join(steps),
        ),
        tag("slides", "\n\n".join(slides)),
    ]
    if kind == "retrospective":
        struggles = [
            f"{s['question']} (hints: {s['hints']})"
            for raw in slides
            for s in json.loads(raw)["struggled"]
        ]
        blocks.append(tag("struggles", "\n".join(struggles) or "none recorded"))
    return "\n\n".join([*blocks, *([tag("instruction", instruction)] if instruction else [])])


async def _write(project_id: int, message: str, step_id: int | None) -> Slide:
    return await client.structured(
        "slide_writer",
        user_message(message),
        Slide,
        project_id=project_id,
        step_id=step_id,
    )


def _save(
    conn: sqlite3.Connection,
    project_id: int,
    kind: Kind,
    slide: Slide,
    step_id: int | None,
    position: int,
) -> None:
    existing = conn.execute(
        "SELECT id FROM slides WHERE project_id = ? AND kind = ? AND step_id IS ?",
        (project_id, kind, step_id),
    ).fetchone()
    data = slide.model_dump_json(by_alias=True)
    if existing:
        conn.execute(
            "UPDATE slides SET json = ?, notes = ? WHERE id = ?", (data, slide.notes, existing[0])
        )
    else:
        conn.execute(
            "INSERT INTO slides (project_id, step_id, kind, position, json, notes)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, step_id, kind, position, data, slide.notes),
        )


async def write_step_slide(step_id: int, instruction: str | None = None) -> None:
    with db.session() as conn:
        step = runner._step(conn, step_id)
        message = _step_message(conn, step, instruction)
    slide = await _write(step["project_id"], message, step_id)
    with db.session() as conn:
        _save(conn, step["project_id"], "step", slide, step_id, 100 + step["position"])


async def write_project_slide(project_id: int, kind: Kind, instruction: str | None = None) -> None:
    with db.session() as conn:
        message = _project_message(conn, project_id, kind, instruction)
    slide = await _write(project_id, message, None)
    position = {"title": 0, "overview": 1, "retrospective": 10_000}[kind]
    with db.session() as conn:
        _save(conn, project_id, kind, slide, None, position)


async def ensure_project_slides(project_id: int) -> None:
    for kind in ("title", "overview", "retrospective"):
        with db.session() as conn:
            exists = conn.execute(
                "SELECT 1 FROM slides WHERE project_id = ? AND kind = ?", (project_id, kind)
            ).fetchone()
        if not exists:
            await write_project_slide(project_id, kind)


def _slide_row(conn: sqlite3.Connection, slide_id: int) -> sqlite3.Row:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM slides WHERE id = ?", (slide_id,)
    ).fetchone()
    if row is None:
        raise NotFound(f"Slide {slide_id} does not exist.")
    return row


async def regenerate(slide_id: int, instruction: str) -> None:
    with db.session() as conn:
        row = _slide_row(conn, slide_id)
    if row["kind"] == "step":
        await write_step_slide(row["step_id"], instruction)
    else:
        await write_project_slide(row["project_id"], row["kind"], instruction)


def edit(slide_id: int, slide: Slide) -> None:
    with db.session() as conn:
        _slide_row(conn, slide_id)
        conn.execute(
            "UPDATE slides SET json = ?, notes = ? WHERE id = ?",
            (slide.model_dump_json(by_alias=True), slide.notes, slide_id),
        )


def reorder(project_id: int, slide_ids: list[int]) -> None:
    with db.session() as conn:
        current = {r["id"] for r in conn.execute(
            "SELECT id FROM slides WHERE project_id = ?", (project_id,)
        )}  # fmt: skip
        if set(slide_ids) != current or len(slide_ids) != len(current):
            raise Conflict("The new order must list every slide of this deck once.")
        conn.executemany(
            "UPDATE slides SET position = ? WHERE id = ?",
            [(i, sid) for i, sid in enumerate(slide_ids)],
        )


def code_lines(conn: sqlite3.Connection, row: sqlite3.Row, slide: dict[str, Any]) -> list[str]:
    """Code visuals show the committed file, never text the model wrote."""
    spec = slide["visual"]["spec"]
    step = conn.execute("SELECT * FROM steps WHERE id = ?", (row["step_id"],)).fetchone()
    if step is None or not step["commit_sha"]:
        return []
    repo = runner._repo(conn, step["project_id"])
    try:
        lines = git.file_at(repo, step["commit_sha"], spec["path"]).splitlines()
    except NotFound:
        return []
    start, end = spec["lines"]
    return lines[max(start, 1) - 1 : end]


def deck(project_id: int) -> list[dict[str, Any]]:
    with db.session() as conn:
        rows = conn.execute(
            "SELECT * FROM slides WHERE project_id = ? ORDER BY position, id", (project_id,)
        ).fetchall()
        out = []
        for row in rows:
            slide = json.loads(row["json"])
            code = code_lines(conn, row, slide) if slide["visual"]["kind"] == "code" else None
            out.append({"id": row["id"], "kind": row["kind"], "slide": slide, "code": code})
    return out


def repo_for(project_id: int) -> Path:
    with db.session() as conn:
        return runner._repo(conn, project_id)


Format = Literal["pptx", "pdf"]


def export_deck(project_id: int, fmt: Format) -> dict[str, Any]:
    """Write deck_v<n>.<fmt>; earlier versions stay downloadable (SPEC section 7)."""
    entries = deck(project_id)
    if not entries:
        raise Conflict("There are no slides to export yet.")
    with db.session() as conn:
        version = (
            1
            + conn.execute(
                "SELECT COUNT(*) FROM deck_exports WHERE project_id = ? AND format = ?",
                (project_id, fmt),
            ).fetchone()[0]
        )
    path = vcpg_home() / "exports" / str(project_id) / f"deck_v{version}.{fmt}"
    (pptx.export if fmt == "pptx" else pdf.export)(entries, path)
    with db.session() as conn:
        conn.execute(
            "INSERT INTO deck_exports (project_id, version, format, path) VALUES (?, ?, ?, ?)",
            (project_id, version, fmt, str(path)),
        )
    return {"version": version, "format": fmt}


def exports(project_id: int) -> list[dict[str, Any]]:
    with db.session() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT id, version, format, created_at FROM deck_exports WHERE project_id = ?"
                " ORDER BY id DESC",
                (project_id,),
            )
        ]


def export_path(export_id: int) -> Path:
    with db.session() as conn:
        row = conn.execute("SELECT path FROM deck_exports WHERE id = ?", (export_id,)).fetchone()
    if row is None or not Path(row["path"]).exists():
        raise NotFound(f"Export {export_id} does not exist.")
    return Path(row["path"])
