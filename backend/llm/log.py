"""Record every agent call: a row in agent_calls, full input and output as redacted files."""

import json
from typing import Any
from uuid import uuid4

from backend import db
from backend.llm.config import AgentConfig
from backend.paths import vcpg_home
from backend.redact import redact


def _write(content: Any) -> str:
    logs = vcpg_home() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{uuid4().hex}.json"
    path.write_text(redact(json.dumps(content, ensure_ascii=False, indent=1)), encoding="utf-8")
    return str(path)


def record(
    agent: str,
    cfg: AgentConfig,
    *,
    request: Any,
    output: str | None,
    error: str | None,
    duration_ms: int,
    project_id: int | None,
    step_id: int | None,
) -> None:
    with db.session() as conn:
        conn.execute(
            "INSERT INTO agent_calls (agent, model, effort, runtime, project_id, step_id,"
            " input_ref, output_ref, ok, error, duration_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                agent,
                cfg.model,
                cfg.effort,
                cfg.runtime,
                project_id,
                step_id,
                _write(request),
                _write(output) if output is not None else None,
                error is None,
                redact(error) if error else None,
                duration_ms,
            ),
        )
