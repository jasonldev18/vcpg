import asyncio
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from backend import redact
from backend.events import bus
from backend.llm import client, sdk
from backend.llm.client import LLMError, Message, OnText, Reply
from backend.llm.config import AgentConfig
from backend.schemas import BuildNote, CommandRun, Cut, FileChange, ReviewNote

FIXTURES = Path(__file__).parent / "fixtures" / "llm"


class MemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if self.store.pop((service, username), None) is None:
            raise PasswordDeleteError(username)


class FakeLLM:
    """Replays recorded replies per agent and keeps every request for assertions."""

    def __init__(self) -> None:
        self.replies: defaultdict[str, deque[Reply]] = defaultdict(deque)
        self.requests: list[tuple[str, list[Message], dict[str, Any]]] = []

    def reply(self, agent: str, text: str, stop_reason: str = "end_turn") -> None:
        self.replies[agent].append(Reply(text, stop_reason))

    def reply_fixture(self, agent: str, name: str) -> None:
        self.reply(agent, (FIXTURES / name).read_text(encoding="utf-8"))

    def requests_for(self, agent: str) -> list[list[Message]]:
        return [messages for a, messages, _ in self.requests if a == agent]

    async def __call__(
        self,
        agent: str,
        cfg: AgentConfig,
        system: str,
        messages: list[Message],
        output_config: dict[str, Any],
        on_text: OnText,
    ) -> Reply:
        self.requests.append((agent, messages, output_config))
        if not self.replies[agent]:
            raise AssertionError(f"no recorded reply left for {agent}")
        reply = self.replies[agent].popleft()
        half = len(reply.text) // 2
        on_text(reply.text[:half])
        on_text(reply.text[half:])
        return reply


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Never touch the real ~/.vcpg from tests."""
    monkeypatch.setenv("VCPG_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def memory_keyring(request: pytest.FixtureRequest) -> Iterator[MemoryKeyring | None]:
    """Never touch the real OS keychain from unit tests; live tests need the saved key."""
    if request.node.get_closest_marker("live"):
        yield None
        return
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)
    redact._known.clear()


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    fake = FakeLLM()
    monkeypatch.setattr(client, "transport", fake)
    return fake


@pytest.fixture(autouse=True)
def fresh_bus() -> None:
    """Project IDs restart in every test database, so stale events must not replay."""
    bus.__init__()  # type: ignore[misc]


class FakeBuilder:
    """Stands in for Agent SDK builder and reviewer sessions. The builder writes a real file;
    the reviewer passes unless a "fail" verdict is queued in `reviews`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.release = threading.Event()
        self.release.set()
        self.fail: str | None = None
        self.reviews: deque[str] = deque()

    async def __call__(
        self, agent: str, task: str, cwd: Path, schema: type[Any], **kw: Any
    ) -> BuildNote | ReviewNote:
        self.calls.append({"agent": agent, "task": task, "cwd": cwd, **kw})
        if agent == "reviewer":
            verdict = self.reviews.popleft() if self.reviews else "pass"
            return ReviewNote(
                commands=[CommandRun(cmd="pytest -q", result=verdict, summary="ran tests")],
                cut=[Cut(path="app.py", what="unused import os", why="nothing uses it")],
                fixed=[],
                status=verdict,
                failure="test_x fails: off by one" if verdict == "fail" else None,
            )
        (cwd / f"step_{kw['step_id']}.py").write_text("x = 1\n", encoding="utf-8")
        while not self.release.is_set():  # the test thread releases it
            await asyncio.sleep(0.01)
        if self.fail:
            raise LLMError(self.fail)
        return BuildNote(
            files=[FileChange(path=f"step_{kw['step_id']}.py", summary="adds x")],
            decisions=["kept it small"],
            not_done=[],
        )

    def agents(self) -> list[str]:
        return [c["agent"] for c in self.calls]


@pytest.fixture
def fake_builder(monkeypatch: pytest.MonkeyPatch) -> FakeBuilder:
    fake = FakeBuilder()
    monkeypatch.setattr(sdk, "run_agent", fake)
    return fake


def wait_for(check: Callable[[], bool], timeout: float = 5) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting")
        time.sleep(0.02)
