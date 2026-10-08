"""run_agent with a replayed session: the real hook, guard, pause gate, env and validation."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    UserMessage,
)

from backend import db
from backend.events import bus
from backend.llm import sdk
from backend.llm.client import LLMError
from backend.schemas import BuildNote

NOTE = {"files": [{"path": "app.py", "summary": "adds main"}], "decisions": [], "not_done": []}


class Replay:
    """Plays scripted sessions; each tool attempt goes through the real PreToolUse hook."""

    def __init__(self, *sessions: tuple[list[tuple[str, dict[str, Any]]], Any]) -> None:
        self.sessions = list(sessions)
        self.options: list[ClaudeAgentOptions] = []
        self.decisions: list[str | None] = []

    async def __call__(self, *, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[Any]:
        self.options.append(options)
        attempts, structured = self.sessions.pop(0)
        hook = options.hooks["PreToolUse"][0].hooks[0]  # type: ignore[index]
        yield AssistantMessage(content=[TextBlock(text="Working on it.")], model="m")
        for name, tool_input in attempts:
            out = await hook(
                {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": tool_input},
                "id",
                {"signal": None},
            )
            decision = out.get("hookSpecificOutput", {}).get("permissionDecision")
            self.decisions.append(decision)
            yield UserMessage(content=[ToolResultBlock(tool_use_id="id", content="done")])
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-1",
            structured_output=structured,
        )


@pytest.fixture
def project(tmp_path: Path) -> int:
    with db.session() as conn:
        pid = conn.execute(
            "INSERT INTO projects (name, brief, start_path) VALUES ('p', 'b', 'plan')"
        ).lastrowid
        sid = conn.execute(
            "INSERT INTO steps (project_id, position, title, component, goal)"
            " VALUES (?, 0, 's', 'backend', 'g')",
            (pid,),
        ).lastrowid
    assert pid and sid
    return pid


async def run(project: int, replay: Replay, monkeypatch: pytest.MonkeyPatch, cwd: Path) -> Any:
    monkeypatch.setattr(sdk, "run_query", replay)
    go = asyncio.Event()
    go.set()
    return await sdk.run_agent(
        "builder", "build it", cwd, BuildNote,
        project_id=project, step_id=1, allow_install=True, resume=go,
    )  # fmt: skip


async def test_guard_denies_inside_a_session_and_the_note_is_validated(
    project: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    replay = Replay(([("Write", {"file_path": "app.py"}), ("Bash", {"command": "git push"})], NOTE))
    events = bus.subscribe(project)
    note = await run(project, replay, monkeypatch, tmp_path)
    assert note == BuildNote.model_validate(NOTE)
    assert replay.decisions == [None, "deny"]
    seen = [await asyncio.wait_for(anext(events), 1) for _ in range(7)]
    tool_events = [e.data for e in seen if e.type == "tool_use"]
    assert [t["summary"] for t in tool_events] == ["Write app.py", "Bash git push"]
    assert tool_events[1]["denied"]


async def test_session_options_lock_the_agent_down(
    project: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_be_blanked")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-be-replaced")
    replay = Replay(([], NOTE))
    await run(project, replay, monkeypatch, tmp_path)
    [options] = replay.options
    assert options.setting_sources == []
    assert options.cwd == str(tmp_path)
    assert set(options.tools) == {"Read", "Write", "Edit", "Glob", "Grep", "Bash"}  # type: ignore[arg-type]
    assert "WebFetch" in options.disallowed_tools
    assert options.env["GITHUB_TOKEN"] == ""
    assert options.env["ANTHROPIC_API_KEY"] not in ("", "sk-ant-should-be-replaced")
    assert options.env["ANTHROPIC_BASE_URL"].startswith("http://127.0.0.1:")
    assert (options.model, options.effort, options.max_turns) == ("claude-opus-5-5", "high", 60)


async def test_invalid_note_is_retried_once_in_the_same_session(
    project: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    replay = Replay(([], {"files": "nope"}), ([], NOTE))
    note = await run(project, replay, monkeypatch, tmp_path)
    assert note.files[0].path == "app.py"
    assert replay.options[1].resume == "session-1"


async def test_two_invalid_notes_fail(
    project: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    replay = Replay(([], {}), ([], {}))
    with pytest.raises(LLMError, match="invalid note twice"):
        await run(project, replay, monkeypatch, tmp_path)


async def test_pause_holds_the_next_tool_call(
    project: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    replay = Replay(([("Read", {"file_path": "a.py"})], NOTE))
    monkeypatch.setattr(sdk, "run_query", replay)
    gate = asyncio.Event()  # paused
    task = asyncio.create_task(
        sdk.run_agent(
            "builder",
            "x",
            tmp_path,
            BuildNote,
            project_id=project,
            step_id=1,
            allow_install=False,
            resume=gate,
        )
    )
    await asyncio.sleep(0.3)
    assert not task.done() and replay.decisions == []
    gate.set()
    await task
    assert replay.decisions == [None]


async def test_audit_sessions_are_read_only_with_the_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    replay = Replay(
        (
            [
                ("Read", {"file_path": str(logs / "1.json")}),
                ("Write", {"file_path": "prompts/grader.md", "content": "x"}),
                ("mcp__vcpg__run_in_sandbox", {"command": "pytest"}),
            ],
            NOTE,
        )
    )
    monkeypatch.setattr(sdk, "run_query", replay)
    go = asyncio.Event()
    go.set()
    await sdk.run_agent(
        "bolt", "audit", tmp_path, BuildNote,
        project_id=None, step_id=None, allow_install=False, resume=go, read_only=(logs,),
    )  # fmt: skip
    [options] = replay.options
    assert options.tools == ["Read", "Glob", "Grep"] and options.mcp_servers == {}
    assert options.add_dirs == [logs]
    assert replay.decisions == [None, "deny", "deny"]
    with db.session() as conn:
        row = conn.execute("SELECT agent, project_id FROM agent_calls").fetchone()
    assert (row["agent"], row["project_id"]) == ("bolt", None)
