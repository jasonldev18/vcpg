import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import BaseModel

from backend import db, secrets
from backend.events import bus
from backend.llm import client
from backend.llm.client import LLMError, MissingKey
from tests.conftest import FakeLLM

FAKE_KEY = "sk-ant-api03-test-key-0000"


class Verdict(BaseModel):
    ok: bool
    reason: str


def calls() -> list[sqlite3.Row]:
    with db.session() as conn:
        return conn.execute("SELECT * FROM agent_calls ORDER BY id").fetchall()


async def test_text_streams_deltas_to_the_project_and_logs_the_call(fake_llm: FakeLLM) -> None:
    fake_llm.reply("tutor", "Normalization puts features on one scale.")
    with db.session() as conn:
        pid = conn.execute(
            "INSERT INTO projects (name, brief, start_path) VALUES ('p', 'b', 'plan')"
        ).lastrowid
    assert pid is not None
    seen = []
    events = bus.subscribe(project_id=pid)

    msgs = [{"role": "user", "content": "hi"}]
    out = await client.text("tutor", msgs, project_id=pid, stream=True)

    for _ in range(4):
        seen.append(await anext(events))
    assert out == "Normalization puts features on one scale."
    assert [e.type for e in seen] == ["agent_started", "agent_text", "agent_text", "agent_finished"]
    assert "".join(e.data["text"] for e in seen if e.type == "agent_text") == out
    [row] = calls()
    assert (row["agent"], row["model"], row["effort"], row["ok"]) == (
        "tutor",
        "claude-sonnet-5-5",
        "high",
        1,
    )
    assert fake_llm.requests[0][2] == {"effort": "high"}


async def test_structured_sends_schema_and_parses(fake_llm: FakeLLM) -> None:
    fake_llm.reply("grader", '{"ok": true, "reason": "clear"}')
    out = await client.structured("grader", [{"role": "user", "content": "x"}], Verdict)
    assert out == Verdict(ok=True, reason="clear")
    fmt = fake_llm.requests[0][2]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["required"] == ["ok", "reason"]


async def test_structured_retries_once_with_the_validation_error(fake_llm: FakeLLM) -> None:
    fake_llm.reply("grader", '{"ok": "maybe"}')
    fake_llm.reply("grader", '{"ok": false, "reason": "fixed"}')
    out = await client.structured("grader", [{"role": "user", "content": "x"}], Verdict)
    assert out.reason == "fixed"
    retry = fake_llm.requests_for("grader")[1]
    assert retry[1] == {"role": "assistant", "content": '{"ok": "maybe"}'}
    assert "reason" in retry[2]["content"] and "Field required" in retry[2]["content"]


async def test_structured_gives_up_after_second_invalid_reply(fake_llm: FakeLLM) -> None:
    fake_llm.reply("grader", "not json")
    fake_llm.reply("grader", "still not json")
    with pytest.raises(LLMError, match="invalid JSON twice"):
        await client.structured("grader", [{"role": "user", "content": "x"}], Verdict)
    assert len(calls()) == 2


async def test_refusal_raises_and_is_logged_as_failed(fake_llm: FakeLLM) -> None:
    fake_llm.reply("interviewer", "", stop_reason="refusal")
    with pytest.raises(LLMError, match="declined"):
        await client.text("interviewer", [{"role": "user", "content": "x"}])
    [row] = calls()
    assert row["ok"] == 0 and "declined" in row["error"]


async def test_log_files_never_contain_the_key(fake_llm: FakeLLM) -> None:
    secrets.save("anthropic", FAKE_KEY)
    fake_llm.reply("tutor", f"echo {FAKE_KEY}")
    await client.text("tutor", [{"role": "user", "content": f"my key is {FAKE_KEY}"}])
    [row] = calls()
    for ref in (row["input_ref"], row["output_ref"]):
        content = Path(ref).read_text(encoding="utf-8")
        assert FAKE_KEY not in content
        assert "[redacted]" in content
    assert json.loads(Path(row["input_ref"]).read_text())["messages"][0]["role"] == "user"


async def test_real_transport_without_a_saved_key_fails_before_any_network_call() -> None:
    with pytest.raises(MissingKey):
        await client.text("tutor", [{"role": "user", "content": "x"}])
    [row] = calls()
    assert row["ok"] == 0
