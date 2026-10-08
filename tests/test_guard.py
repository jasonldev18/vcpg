import os
from pathlib import Path

import pytest

from backend.llm.guard import SANDBOX_TOOL, check


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    (root / "app").mkdir(parents=True)
    (root / ".git").mkdir()
    return root


ALLOWED = [
    ("Read", {"file_path": "app/main.py"}),
    ("Write", {"file_path": "app/new.py", "content": "x = 1"}),
    ("Edit", {"file_path": "README.md", "old_string": "a", "new_string": "b"}),
    ("Glob", {"pattern": "**/*.py"}),
    ("Grep", {"pattern": "def ", "path": "app", "glob": "*.py"}),
    ("Bash", {"command": "git diff"}),
    ("Bash", {"command": "git status --short"}),
    ("Bash", {"command": "ls app"}),
    (SANDBOX_TOOL, {"command": "pytest -q"}),
    (SANDBOX_TOOL, {"command": "python -m app.main --user 3"}),
    (SANDBOX_TOOL, {"command": "pip install pandas==2.2"}),
    (SANDBOX_TOOL, {"command": "rm -rf build"}),
    ("StructuredOutput", {"files": [], "decisions": [], "not_done": []}),
]

DENIED = [
    # writes and reads outside the workspace
    ("Write", {"file_path": "../escape.py", "content": "x"}),
    ("Write", {"file_path": str(Path.home() / "evil.py"), "content": "x"}),
    ("Read", {"file_path": str(Path.home() / ".ssh" / "id_rsa")}),
    ("Read", {"file_path": "~/.ssh/id_rsa"}),
    ("Glob", {"pattern": "../**/*"}),
    ("Grep", {"pattern": "key", "path": "/"}),
    # history belongs to the orchestrator
    ("Write", {"file_path": ".git/config", "content": "x"}),
    ("Edit", {"file_path": "app/../.git/HEAD", "old_string": "a", "new_string": "b"}),
    # git writes and network
    ("Bash", {"command": "git push origin main"}),
    ("Bash", {"command": "git reset --hard HEAD~1"}),
    ("Bash", {"command": "git status; git push"}),
    ("Bash", {"command": "git diff --output=out.txt"}),
    ("Bash", {"command": "curl https://example.com"}),
    ("Bash", {"command": "printenv"}),
    ("Bash", {"command": "cat ~/.ssh/id_rsa"}),
    (SANDBOX_TOOL, {"command": "git push"}),
    (SANDBOX_TOOL, {"command": "git reset --hard"}),
    (SANDBOX_TOOL, {"command": "git commit -am x"}),
    (SANDBOX_TOOL, {"command": "curl https://example.com"}),
    (SANDBOX_TOOL, {"command": "wget https://example.com"}),
    (SANDBOX_TOOL, {"command": "printenv"}),
    (SANDBOX_TOOL, {"command": "env"}),
    (SANDBOX_TOOL, {"command": "set"}),
    (SANDBOX_TOOL, {"command": "python -c 'import keyring'"}),
    (SANDBOX_TOOL, {"command": "cat ~/.ssh/id_rsa"}),
    (SANDBOX_TOOL, {"command": "rm -rf /"}),
    (SANDBOX_TOOL, {"command": "rm -rf ../other-project"}),
    (SANDBOX_TOOL, {"command": r"type C:\Users\me\secrets.txt"}),
    (SANDBOX_TOOL, {"command": "powershell -c Invoke-WebRequest x"}),
    # tools that are not part of the session
    ("WebFetch", {"url": "https://example.com"}),
    ("WebSearch", {"query": "x"}),
    ("Task", {"prompt": "x"}),
]


@pytest.mark.parametrize(("tool", "tool_input"), ALLOWED)
def test_allowed(ws: Path, tool: str, tool_input: dict[str, str]) -> None:
    assert check(tool, tool_input, ws) is None


@pytest.mark.parametrize(("tool", "tool_input"), DENIED)
def test_denied(ws: Path, tool: str, tool_input: dict[str, str]) -> None:
    assert check(tool, tool_input, ws) is not None


def test_symlink_that_resolves_outside_is_denied(ws: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        os.symlink(outside, ws / "link", target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks needs Developer Mode on Windows")
    assert check("Write", {"file_path": "link/x.py", "content": "x"}, ws) is not None


def test_audit_sessions_read_the_logs_but_never_write(ws: Path, tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    audit = {"read_roots": (logs,), "can_write": False}
    assert check("Read", {"file_path": str(logs / "call.json")}, ws, **audit) is None  # type: ignore[arg-type]
    assert check("Grep", {"pattern": "hint", "path": str(logs)}, ws, **audit) is None  # type: ignore[arg-type]
    assert check("Read", {"file_path": "app/main.py"}, ws, **audit) is None  # type: ignore[arg-type]
    assert check("Write", {"file_path": "app/x.py", "content": "x"}, ws, **audit) is not None  # type: ignore[arg-type]
    assert check("Edit", {"file_path": str(logs / "call.json")}, ws, **audit) is not None  # type: ignore[arg-type]
    assert (
        check("Read", {"file_path": str(Path.home() / ".ssh" / "id_rsa")}, ws, **audit) is not None
    )  # type: ignore[arg-type]
    assert check("Bash", {"command": "git status"}, ws, **audit) is not None  # type: ignore[arg-type]
    assert check(SANDBOX_TOOL, {"command": "pytest"}, ws, **audit) is not None  # type: ignore[arg-type]
    # builders never get the logs, even for reading
    assert check("Read", {"file_path": str(logs / "call.json")}, ws) is not None
