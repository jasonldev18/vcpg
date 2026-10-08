"""PreToolUse rules for builder and reviewer sessions (SECURITY.md section 4).

Enforced on top of the SDK's allowed/disallowed tool lists: anything these rules do not allow
is denied, even if the tool lists would let it through.
"""

import re
from pathlib import Path
from typing import Any

SANDBOX_TOOL = "mcp__vcpg__run_in_sandbox"
FILE_TOOLS = {"Read", "Write", "Edit", "Glob", "Grep"}
RESULT_TOOL = "StructuredOutput"  # how the SDK returns the final JSON; it touches nothing
PATH_FIELDS = ("file_path", "path", "notebook_path")

CHAINING = re.compile(r"[;&|`$<>(){}\n]")
ABSOLUTE_OR_PARENT = re.compile(r"(^|[\s=\"'])(/|~|[A-Za-z]:[\\/]|\\\\)|\.\.")
BASH_ALLOWED = re.compile(r"^(git (diff|status)|ls)(\s|$)")
ALWAYS_DENIED = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bgit\s+(?!(diff|status|log|show)\b)\S+",  # only read-only git subcommands
        r"\b(curl|wget|ssh|scp|gh|printenv|keyring|powershell|pwsh|bitsadmin|certutil)\b",
        r"\binvoke-(webrequest|restmethod)\b",
        r"(^|[\s;&|(])(env|security|set)(\s|$)",
        r"\.ssh\b|keychain|--output",
    )
]


def _outside(cwd: Path, raw: str) -> str | None:
    path = Path(raw).expanduser()  # the CLI expands ~ itself
    resolved = (path if path.is_absolute() else cwd / path).resolve()  # follows symlinks
    root = cwd.resolve()
    if not resolved.is_relative_to(root):
        return f"{raw} is outside the project workspace."
    if ".git" in resolved.relative_to(root).parts:
        return "The .git folder is off limits; the orchestrator owns history."
    return None


def _command(command: str, bash: bool) -> str | None:
    command = command.strip()
    if bash and (not BASH_ALLOWED.match(command) or CHAINING.search(command)):
        return "Bash is limited to `git diff`, `git status` and `ls`; use run_in_sandbox for code."
    if ABSOLUTE_OR_PARENT.search(command):
        return "Commands may only use paths inside the workspace (no absolute paths, ~ or ..)."
    for pattern in ALWAYS_DENIED:
        if pattern.search(command):
            return f"`{command}` is not allowed in this session."
    return None


def check(tool: str, tool_input: dict[str, Any], cwd: Path) -> str | None:
    """Return why a tool call is denied, or None to allow it."""
    if tool == "Bash":
        return _command(str(tool_input.get("command", "")), bash=True)
    if tool == SANDBOX_TOOL:
        return _command(str(tool_input.get("command", "")), bash=False)
    if tool == RESULT_TOOL:
        return None
    if tool not in FILE_TOOLS:
        return f"The {tool} tool is not available in this session."
    for field in PATH_FIELDS:
        if field in tool_input and (reason := _outside(cwd, str(tool_input[field]))):
            return reason
    for field in ("pattern", "glob") if tool == "Glob" else ("glob",):
        value = str(tool_input.get(field, ""))
        if ".." in value or Path(value).is_absolute() or value.startswith("~"):
            return "Search patterns must stay inside the workspace."
    return None
