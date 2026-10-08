"""Every Messages API call goes through here: config, prompt, streaming, validation, logs."""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

import anthropic
from anthropic.types import MessageParam
from pydantic import BaseModel, ValidationError

from backend import db, secrets
from backend.events import bus
from backend.llm import log
from backend.llm.config import AgentConfig, load
from backend.llm.prompts import prompt

Message = dict[str, Any]
OnText = Callable[[str], None]


class LLMError(Exception):
    pass


class MissingKey(LLMError):
    pass


@dataclass(frozen=True)
class Reply:
    text: str
    stop_reason: str | None


async def _anthropic(
    agent: str,
    cfg: AgentConfig,
    system: str,
    messages: list[Message],
    output_config: dict[str, Any],
    on_text: OnText,
) -> Reply:
    key = secrets.get("anthropic")
    if not key:
        raise MissingKey("Add your Anthropic API key in Core access first.")
    client = anthropic.AsyncAnthropic(api_key=key)
    async with client.messages.stream(
        model=cfg.model,
        max_tokens=cfg.max_tokens or 0,
        system=system,
        messages=cast(list[MessageParam], messages),
        output_config=cast(Any, output_config),
    ) as stream:
        async for delta in stream.text_stream:
            on_text(delta)
        final = await stream.get_final_message()
    text = "".join(block.text for block in final.content if block.type == "text")
    return Reply(text, final.stop_reason)


Transport = Callable[
    [str, AgentConfig, str, list[Message], dict[str, Any], OnText], Awaitable[Reply]
]
transport: Transport = _anthropic  # unit tests swap in recorded replies


async def _call(
    agent: str,
    messages: list[Message],
    output_config: dict[str, Any],
    *,
    project_id: int | None,
    step_id: int | None,
    stream: bool,
) -> str:
    with db.session() as conn:
        cfg = load(agent, conn)

    def on_text(delta: str) -> None:
        if stream and project_id is not None:
            bus.publish(project_id, "agent_text", agent=agent, text=delta)

    if project_id is not None:
        bus.publish(project_id, "agent_started", agent=agent)
    started, output, error = time.monotonic(), None, None
    try:
        reply = await transport(
            agent, cfg, prompt(agent), messages, {"effort": cfg.effort, **output_config}, on_text
        )
        output = reply.text
        if reply.stop_reason == "refusal":
            raise LLMError(f"The {agent} declined this request.")
        return reply.text
    except anthropic.APIError as e:
        error = f"{type(e).__name__}: {e.message}"
        raise LLMError(f"The {agent} call failed: {e.message}") from e
    except LLMError as e:
        error = str(e)
        raise
    finally:
        log.record(
            agent,
            cfg,
            request={"messages": messages, "output_config": output_config},
            output=output,
            error=error,
            duration_ms=int((time.monotonic() - started) * 1000),
            project_id=project_id,
            step_id=step_id,
        )
        if project_id is not None:
            bus.publish(project_id, "agent_finished", agent=agent, ok=error is None)


async def text(
    agent: str,
    messages: list[Message],
    *,
    project_id: int | None = None,
    step_id: int | None = None,
    stream: bool = False,
) -> str:
    return await _call(agent, messages, {}, project_id=project_id, step_id=step_id, stream=stream)


async def structured[T: BaseModel](
    agent: str,
    messages: list[Message],
    schema: type[T],
    *,
    project_id: int | None = None,
    step_id: int | None = None,
) -> T:
    """Ask for JSON matching `schema`; on a validation error, retry once with the error."""
    fmt = {"format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)}}
    ids: dict[str, Any] = {"project_id": project_id, "step_id": step_id, "stream": False}
    out = await _call(agent, messages, fmt, **ids)
    try:
        return schema.model_validate_json(out)
    except ValidationError as e:
        retry = [
            *messages,
            {"role": "assistant", "content": out or "(empty)"},
            {
                "role": "user",
                "content": f"That JSON failed validation:\n{e}\nReturn corrected JSON only.",
            },
        ]
        out = await _call(agent, retry, fmt, **ids)
    try:
        return schema.model_validate_json(out)
    except ValidationError as e:
        raise LLMError(f"The {agent} returned invalid JSON twice.") from e


async def check_key(key: str) -> None:
    """One free call (list models) to confirm the key works before it is saved."""
    try:
        await anthropic.AsyncAnthropic(api_key=key, max_retries=0).models.list(limit=1)
    except anthropic.AuthenticationError as e:
        raise LLMError("Anthropic rejected this key.") from e
    except anthropic.APIError as e:
        raise LLMError(f"Could not reach Anthropic: {e.message}") from e
