import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app import TOKEN_HEADER, create_app
from backend.events import Bus
from backend.llm import client
from backend.llm.client import LLMError
from backend.routes.events import sse

KEY = "sk-ant-api03-real-looking-key-WXYZ"


@pytest.fixture
def api() -> Iterator[TestClient]:
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as c:
        c.headers[TOKEN_HEADER] = c.get("/api/session").json()["token"]
        yield c


@pytest.fixture
def key_check(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    checked: list[str] = []

    async def check(key: str) -> None:
        checked.append(key)
        if "bad" in key:
            raise LLMError("Anthropic rejected this key.")

    monkeypatch.setattr(client, "check_key", check)
    return checked


def test_key_is_tested_before_saving_and_never_returned(
    api: TestClient, key_check: list[str]
) -> None:
    assert api.get("/api/core/anthropic").json() == {"saved": False, "last4": None}
    saved = api.put("/api/core/anthropic", json={"key": f"  {KEY} "})
    assert saved.json() == {"saved": True, "last4": "WXYZ"}
    assert key_check == [KEY]
    assert KEY not in api.get("/api/core/anthropic").text
    assert api.post("/api/core/anthropic/test").json()["saved"] is True


def test_a_rejected_key_is_not_saved(api: TestClient, key_check: list[str]) -> None:
    response = api.put("/api/core/anthropic", json={"key": "sk-ant-bad-key-0000"})
    assert response.status_code == 502
    assert "sk-ant-bad" not in response.text
    assert api.get("/api/core/anthropic").json()["saved"] is False


def test_remove_key(api: TestClient, key_check: list[str]) -> None:
    api.put("/api/core/anthropic", json={"key": KEY})
    assert api.delete("/api/core/anthropic").json() == {"saved": False, "last4": None}


def test_sse_frames_are_redacted() -> None:
    bus = Bus()
    bus.publish(1, "agent_text", text=f"leak {KEY}")
    event = asyncio.run(anext(bus.subscribe(1)))
    frame = sse(event)
    assert frame.startswith("id: 1\nevent: agent_text\ndata: ")
    assert KEY not in frame and "[redacted]" in frame


async def test_subscribe_replays_after_last_event_id_then_streams_live() -> None:
    bus = Bus()
    for n in range(3):
        bus.publish(1, "tick", n=n)
    bus.publish(2, "other")
    stream = bus.subscribe(1, after_id=1)
    assert [(await anext(stream)).data["n"] for _ in range(2)] == [1, 2]
    bus.publish(1, "tick", n=3)
    assert (await anext(stream)).data == {"n": 3}
