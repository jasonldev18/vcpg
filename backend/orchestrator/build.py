"""Build runs in the background per step; the user can pause, resume or stop it (SPEC 5.2).

Review is still a stub (phase 3): a finished build is marked reviewed and committed.
"""

import asyncio
import json
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
from backend.schemas import BuildNote
from backend.workspace import git

S = State
REVIEW_STUB = "Review arrives in phase 3; this step was committed without one."


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
    with db.session() as conn:
        step = runner._step(conn, step_id)
        task = _task(conn, step)
    project_id = step["project_id"]
    try:
        cwd = workspace(project_id)
        note = await sdk.run_agent(
            "builder", task, cwd, BuildNote,
            project_id=project_id, step_id=step_id, allow_install=True, resume=resume,
        )  # fmt: skip
        with db.session() as conn:
            conn.execute(
                "UPDATE steps SET build_note = ? WHERE id = ?", (note.model_dump_json(), step_id)
            )
        runner._advance(step_id, S.BUILT)
        _stub_review(step_id, cwd)
    except asyncio.CancelledError:
        bus.publish(project_id, "build_stopped", step_id=step_id)
        raise
    except Exception as e:
        _builds[step_id].error = redact(str(e))
        bus.publish(project_id, "build_failed", step_id=step_id, error=_builds[step_id].error)


def _stub_review(step_id: int, cwd: Path) -> None:
    with db.session() as conn:
        step = runner._step(conn, step_id)
        conn.execute("UPDATE steps SET review_note = ? WHERE id = ?", (REVIEW_STUB, step_id))
    runner._advance(step_id, S.REVIEWED)
    sha = git.commit(cwd, f"step {step['position'] + 1}: {step['title']}")
    with db.session() as conn:
        conn.execute("UPDATE steps SET commit_sha = ? WHERE id = ?", (sha, step_id))


def note(raw: str | None) -> dict[str, Any] | None:
    return json.loads(raw) if raw else None
