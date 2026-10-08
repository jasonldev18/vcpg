from contextvars import ContextVar
from functools import cache
from pathlib import Path

from backend.paths import REPO_ROOT

# An audit run points this at an overlay folder to score a proposed prompt or template change.
root: ContextVar[Path] = ContextVar("prompt_root", default=REPO_ROOT)


@cache
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def prompt(agent: str) -> str:
    return _read(root.get() / "prompts" / f"{agent}.md")
