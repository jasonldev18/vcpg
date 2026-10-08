"""Agent SDK sessions for agents that edit files and run commands (ARCHITECTURE section 5.3)."""

import asyncio
import json
import os
import re
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import anthropic
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookContext,
    HookInput,
    HookJSONOutput,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    UserMessage,
    create_sdk_mcp_server,
    query,
    tool,
)
from pydantic import BaseModel, ValidationError

from backend import db
from backend.events import bus
from backend.llm import guard, log
from backend.llm.client import LLMError
from backend.llm.config import load
from backend.llm.prompts import prompt
from backend.llm.proxy import KeyProxy
from backend.paths import vcpg_home
from backend.redact import redact
from backend.workspace import sandbox

BUILT_IN = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
READ_ONLY = ["Read", "Glob", "Grep"]
AUDIT_CHANNEL = -1  # event bus id for audit runs, which belong to no project
SECRETISH = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH", re.IGNORECASE)
Query = Callable[..., AsyncIterator[Any]]
run_query: Query = query  # unit tests replay recorded sessions


def session_env(proxy: KeyProxy) -> dict[str, str]:
    """Blank every inherited secret-looking variable; the only "key" is the proxy secret."""
    blanked = {name: "" for name in os.environ if SECRETISH.search(name)}
    return blanked | {
        "ANTHROPIC_API_KEY": proxy.secret,
        "ANTHROPIC_BASE_URL": proxy.url,
        "CLAUDE_CONFIG_DIR": str(vcpg_home() / "agent-config"),  # not the user's ~/.claude
        "DISABLE_TELEMETRY": "1",
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }


def summarise(tool_name: str, tool_input: dict[str, Any]) -> str:
    """What the console shows for a tool call: the path or command, never file contents."""
    detail = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("pattern")
    return f"{tool_name.removeprefix('mcp__vcpg__')} {detail or ''}".strip()


async def run_agent[T: BaseModel](
    agent: str,
    task: str,
    cwd: Path,
    schema: type[T],
    *,
    project_id: int | None,
    step_id: int | None,
    allow_install: bool,
    resume: asyncio.Event,
    read_only: tuple[Path, ...] | None = None,
    box: int | None = None,
) -> T:
    """Run one session in `cwd`; return its final JSON, validated, retrying once on error.

    `resume` gates every tool call, so clearing it pauses the agent before its next action.
    `read_only` makes an audit session: Read, Glob and Grep over `cwd` and these extra folders,
    no edits, no shell and no sandbox (SECURITY.md section 4). Its events go to AUDIT_CHANNEL.
    `box` is the sandbox to run commands in when it is not the project's (calibration repos).
    """
    channel = project_id if project_id is not None else AUDIT_CHANNEL
    tools = READ_ONLY if read_only is not None else BUILT_IN
    with db.session() as conn:
        cfg = load(agent, conn)

    @tool(
        "run_in_sandbox",
        "Run a shell command for this project inside its sandbox, with the workspace as the "
        "current directory. Use it for tests, scripts and package installs.",
        {"command": str, "timeout_seconds": int},
    )
    async def run_in_sandbox(args: dict[str, Any]) -> dict[str, Any]:
        result = await sandbox.run(
            box if box is not None else channel,
            args["command"],
            allow_install=allow_install,
            timeout=int(args.get("timeout_seconds") or sandbox.DEFAULT_TIMEOUT),
        )
        text = f"exit code {result.exit_code}\n{result.output}"
        return {"content": [{"type": "text", "text": text}]}

    async def guard_hook(
        hook_input: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        await resume.wait()
        if hook_input["hook_event_name"] != "PreToolUse":
            return {}
        name, tool_input = hook_input["tool_name"], hook_input["tool_input"]
        reason = guard.check(
            name,
            tool_input,
            cwd,
            read_roots=read_only or (),
            can_write=read_only is None,
        )
        bus.publish(
            channel,
            "tool_use",
            agent=agent,
            summary=redact(summarise(name, tool_input)),
            denied=reason,
        )
        if reason is None:
            return {}
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    transcript: list[dict[str, Any]] = []
    started, error = time.monotonic(), None
    bus.publish(channel, "agent_started", agent=agent)
    try:
        async with KeyProxy() as proxy:
            options = ClaudeAgentOptions(
                model=cfg.model,
                effort=cfg.effort,
                system_prompt=prompt(agent),
                cwd=str(cwd),
                tools=tools,
                allowed_tools=tools if read_only is not None else [*tools, guard.SANDBOX_TOOL],
                disallowed_tools=["WebFetch", "WebSearch", "Task", "NotebookEdit"],
                permission_mode="acceptEdits",
                max_turns=cfg.max_turns,
                setting_sources=[],  # never load a CLAUDE.md or settings from the workspace
                hooks={"PreToolUse": [HookMatcher(hooks=[guard_hook], timeout=86_400)]},
                mcp_servers={}
                if read_only is not None
                else {"vcpg": create_sdk_mcp_server("vcpg", tools=[run_in_sandbox])},
                add_dirs=list(read_only or ()),
                env=session_env(proxy),
                output_format={
                    "type": "json_schema",
                    "schema": anthropic.transform_schema(schema),
                },
            )
            result = await _session(options, task, agent, channel, transcript)
            try:
                return schema.model_validate(result.structured_output)
            except ValidationError as e:
                options.resume = result.session_id
                fix = f"Your final JSON failed validation:\n{e}\nReturn the corrected JSON."
                result = await _session(options, fix, agent, channel, transcript)
                try:
                    return schema.model_validate(result.structured_output)
                except ValidationError as e2:
                    raise LLMError(f"The {agent} returned an invalid note twice.") from e2
    except asyncio.CancelledError:
        error = "stopped by the user"
        raise
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        log.record(
            agent,
            cfg,
            request={"task": task, "cwd": str(cwd)},
            output=json.dumps(transcript),
            error=error,
            duration_ms=int((time.monotonic() - started) * 1000),
            project_id=project_id,
            step_id=step_id,
        )
        bus.publish(channel, "agent_finished", agent=agent, ok=error is None)


async def _session(
    options: ClaudeAgentOptions,
    task: str,
    agent: str,
    project_id: int,
    transcript: list[dict[str, Any]],
) -> ResultMessage:
    result: ResultMessage | None = None
    async for message in run_query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    transcript.append({"text": block.text})
                    bus.publish(project_id, "agent_text", agent=agent, text=block.text + "\n")
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    short = redact(str(block.content))[:300]
                    transcript.append({"tool_result": short, "error": bool(block.is_error)})
                    bus.publish(project_id, "tool_result", agent=agent, text=short)
        elif isinstance(message, ResultMessage):
            result = message
    if result is None or result.is_error:
        detail = (result.errors or [result.subtype]) if result else ["no result"]
        raise LLMError(f"The {agent} session failed: {'; '.join(map(str, detail))}")
    return result
