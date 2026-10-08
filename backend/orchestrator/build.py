"""Build and review run in the background per step; the user can pause, resume or stop
them (SPEC 5.2 and 5.3).
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend import db
from backend.errors import Conflict
from backend.events import bus
from backend.llm import sdk
from backend.orchestrator import runner
from backend.orchestrator.context import tag
from backend.orchestrator.machine import State
from backend.redact import redact
from backend.schemas import BuildNote, ReviewNote
from backend.workspace import git, sandbox

S = State
DIFF_LIMIT = 60_000


@dataclass
class Build:
    task: asyncio.Task[None]
    resume: asyncio.Event
    error: str | None = None


_builds: dict[int, Build] = {}


def _running(step_id: int) -> Build | None:
    build = _builds.get(step_id)
    return build if build and not build.task.done() else None


def status(step_id: int) -> dict[str, Any]:
    build = _builds.get(step_id)
    running = _running(step_id)
    return {
        "running": running is not None,
        "paused": running is not None and not running.resume.is_set(),
        "error": build.error if build and not running else None,
        "isolation": "docker" if sandbox.docker_available() else "venv",
    }


def workspace(project_id: int) -> Path:
    """Projects approved before workspaces existed get theirs on first build."""
    with db.session() as conn:
        row = conn.execute(
            "SELECT name, workspace_path FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row["workspace_path"]:
            return Path(row["workspace_path"])
        path = git.init(project_id, row["name"])
        conn.execute("UPDATE projects SET workspace_path = ? WHERE id = ?", (str(path), project_id))
        return path


def ready(step_id: int) -> None:
    """Ready, build it."""
    with db.session() as conn:
        runner._set_state(conn, runner._current(conn, step_id, S.PLANNED), S.TAUGHT)
    start(step_id)


def start(step_id: int) -> None:
    with db.session() as conn:
        runner._current(conn, step_id, S.TAUGHT)
    if _running(step_id):
        raise Conflict("This step is already building.")
    resume = asyncio.Event()
    resume.set()
    _builds[step_id] = Build(asyncio.create_task(_run(step_id, resume)), resume)


def stop(step_id: int) -> None:
    """Stop keeps the workspace as it is; the step stays `taught` until it is built again."""
    build = _running(step_id)
    if build is None:
        raise Conflict("Nothing is building.")
    build.task.cancel()


def pause(step_id: int, paused: bool) -> None:
    build = _running(step_id)
    if build is None:
        raise Conflict("Nothing is building.")
    (build.resume.clear if paused else build.resume.set)()


def _task(conn: Any, step: Any) -> str:
    blocks = [runner._plan_block(conn, step["project_id"]), runner._step_block(step)]
    if step["build_note"] or step["review_note"]:
        blocks.append(
            tag(
                "previous_notes",
                f"Build note:\n{step['build_note'] or 'none'}\n\n"
                f"Review note:\n{step['review_note'] or 'none'}",
            )
        )
    return "\n\n".join(blocks)


async def _run(step_id: int, resume: asyncio.Event) -> None:
    """Build, then review. A failed review sends the step back to the builder once;
    a second failure blocks the step until the user retries or edits the plan."""
    with db.session() as conn:
        project_id = runner._step(conn, step_id)["project_id"]
    try:
        cwd = workspace(project_id)
        base = git.head(cwd)
        for _ in range(2):
            await _build(step_id, cwd, resume)
            runner._advance(step_id, S.BUILT)  # from taught, or built again on the retry
            review = await _review(step_id, cwd, base, resume)
            if review.status == "pass":
                _accept(step_id, cwd)
                return
        runner._advance(step_id, S.BLOCKED)
    except asyncio.CancelledError:
        bus.publish(project_id, "build_stopped", step_id=step_id)
        raise
    except Exception as e:
        _builds[step_id].error = redact(str(e))
        bus.publish(project_id, "build_failed", step_id=step_id, error=_builds[step_id].error)


async def _build(step_id: int, cwd: Path, resume: asyncio.Event) -> None:
    with db.session() as conn:
        step = runner._step(conn, step_id)
        task = _task(conn, step)
    note = await sdk.run_agent(
        "builder", task, cwd, BuildNote,
        project_id=step["project_id"], step_id=step_id, allow_install=True, resume=resume,
    )  # fmt: skip
    with db.session() as conn:
        conn.execute(
            "UPDATE steps SET build_note = ? WHERE id = ?", (note.model_dump_json(), step_id)
        )


async def _review(step_id: int, cwd: Path, base: str, resume: asyncio.Event) -> ReviewNote:
    with db.session() as conn:
        step = runner._step(conn, step_id)
    diff = git.diff_since(cwd, base)
    if len(diff) > DIFF_LIMIT:
        diff = diff[:DIFF_LIMIT] + "\n[diff truncated]"
    task = "\n\n".join(
        [runner._step_block(step), tag("build_note", step["build_note"]), tag("diff", diff)]
    )
    review = await sdk.run_agent(
        "reviewer", task, cwd, ReviewNote,
        project_id=step["project_id"], step_id=step_id, allow_install=False, resume=resume,
    )  # fmt: skip
    with db.session() as conn:
        conn.execute(
            "UPDATE steps SET review_note = ? WHERE id = ?", (review.model_dump_json(), step_id)
        )
    return review


def _accept(step_id: int, cwd: Path) -> None:
    """Review passed: the orchestrator commits the step (ARCHITECTURE section 6)."""
    with db.session() as conn:
        step = runner._step(conn, step_id)
    runner._advance(step_id, S.REVIEWED)
    sha = git.commit(cwd, f"step {step['position'] + 1}: {step['title']}")
    with db.session() as conn:
        conn.execute("UPDATE steps SET commit_sha = ? WHERE id = ?", (sha, step_id))


def retry(step_id: int) -> None:
    """Retry build, from a blocked step."""
    with db.session() as conn:
        runner._set_state(conn, runner._current(conn, step_id, S.BLOCKED), S.TAUGHT)
    start(step_id)
