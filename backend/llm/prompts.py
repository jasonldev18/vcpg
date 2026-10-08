from functools import cache

from backend.paths import REPO_ROOT


@cache
def prompt(agent: str) -> str:
    return (REPO_ROOT / "prompts" / f"{agent}.md").read_text(encoding="utf-8")
