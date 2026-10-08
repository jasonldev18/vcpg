from collections import defaultdict, deque
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from backend import redact
from backend.llm import client
from backend.llm.client import Message, OnText, Reply
from backend.llm.config import AgentConfig

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
