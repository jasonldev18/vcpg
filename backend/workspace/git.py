"""Project workspace repos. Only the orchestrator writes history; agents only read it."""

import subprocess
from pathlib import Path

from backend.errors import NotFound
from backend.paths import vcpg_home

GITIGNORE = """\
.env
.env.*
*.pem
*.key
.venv/
venv/
node_modules/
__pycache__/
*.pyc
.pytest_cache/
.cache/
.local/
dist/
"""
IDENTITY = ["-c", "user.name=VCPG", "-c", "user.email=vcpg@localhost", "-c", "commit.gpgsign=false"]


class GitError(Exception):
    pass


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *IDENTITY, *args], cwd=repo, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        raise GitError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def workspace_path(project_id: int) -> Path:
    return vcpg_home() / "workspaces" / str(project_id)


def init(project_id: int, name: str) -> Path:
    repo = workspace_path(project_id)
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (repo / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    commit(repo, "Start project")
    return repo


def commit(repo: Path, message: str) -> str:
    """Commit everything in the workspace and return the new commit SHA."""
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return head(repo)


def head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").strip()


def diff_since(repo: Path, sha: str) -> str:
    """Working-tree changes (including new files) since `sha`, without staging anything."""
    _git(repo, "add", "-A", "--intent-to-add")
    return _git(repo, "diff", sha)


def show(repo: Path, sha: str) -> str:
    return _git(repo, "show", "--format=%H%n%s%n", sha)


def file_at(repo: Path, sha: str, path: str) -> str:
    try:
        return _git(repo, "show", f"{sha}:{path}")
    except GitError as e:
        raise NotFound(f"{path} is not in this commit.") from e
