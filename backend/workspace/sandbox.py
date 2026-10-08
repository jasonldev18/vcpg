"""Runs generated project code (SECURITY.md section 5).

Docker when it is available: one container per project, network off except for a single
package install during a build. Otherwise a per-project venv with a stripped environment,
which isolates much less; the UI warns about it.
"""

import asyncio
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from backend.paths import vcpg_home
from backend.workspace.git import workspace_path

IMAGE = "python:3.12-slim"
DEFAULT_TIMEOUT = 300
MAX_TIMEOUT = 1200
OUTPUT_LIMIT = 20_000
INSTALL = re.compile(r"^(pip install|uv pip install|npm install)(\s[^;&|`$<>(){}\n]*)?$")


@dataclass(frozen=True)
class Result:
    exit_code: int
    output: str
    timed_out: bool = False


@cache
def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def is_install(command: str) -> bool:
    return INSTALL.match(command.strip()) is not None


# ---- Docker


def _container(project_id: int) -> str:
    return f"vcpg-{project_id}"


def docker_start_argv(project_id: int, workspace: Path) -> list[str]:
    return [
        "docker", "run", "-d", "--name", _container(project_id),
        "--network", "none", "--user", "1000:1000", "--cpus", "2", "--memory", "2g",
        "-v", f"{workspace}:/workspace", "-w", "/workspace",
        "-e", "HOME=/workspace", "-e", "PIP_USER=1",
        "-e", "PYTHONUSERBASE=/workspace/.local",
        "-e", "PATH=/workspace/.local/bin:/usr/local/bin:/usr/bin:/bin",
        IMAGE, "sleep", "infinity",
    ]  # fmt: skip


def docker_exec_argv(project_id: int, command: str) -> list[str]:
    return ["docker", "exec", _container(project_id), "sh", "-c", command]


def _ensure_container(project_id: int) -> None:
    name = _container(project_id)
    running = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name], capture_output=True, text=True
    )
    if running.stdout.strip() == "true":
        return
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    subprocess.run(docker_start_argv(project_id, workspace_path(project_id)), check=True)


def remove_container(project_id: int) -> None:
    if docker_available():
        subprocess.run(["docker", "rm", "-f", _container(project_id)], capture_output=True)


# ---- venv fallback


def venv_dir(project_id: int) -> Path:
    return vcpg_home() / "venvs" / str(project_id)


def stripped_env(project_id: int, network: bool) -> dict[str, str]:
    """Only PATH, HOME (into the workspace) and LANG; no keys. On Windows, user and temp
    folders also point into VCPG's own folders, and SYSTEMROOT, without which Python cannot
    open network sockets, is added only for a package install."""
    venv = venv_dir(project_id)
    scripts = venv / ("Scripts" if sys.platform == "win32" else "bin")
    workspace = workspace_path(project_id)
    env = {
        "PATH": os.pathsep.join([str(scripts), os.environ.get("PATH", "")]),
        "HOME": str(workspace),
        "LANG": "C.UTF-8",
    }
    if sys.platform == "win32":
        temp = vcpg_home() / "tmp" / str(project_id)
        temp.mkdir(parents=True, exist_ok=True)
        env |= {"USERPROFILE": str(workspace), "TEMP": str(temp), "TMP": str(temp)}
        if network:
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return env


def _ensure_venv(project_id: int) -> None:
    if not venv_dir(project_id).exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir(project_id))], check=True)


# ---- running


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()


def _run_blocking(
    argv: list[str] | str, cwd: Path | None, env: dict[str, str] | None, timeout: int
) -> Result:
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        shell=isinstance(argv, str),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        out, _ = proc.communicate()
        timed_out = True
    text = out.decode("utf-8", errors="replace")[-OUTPUT_LIMIT:]
    if timed_out:
        text += f"\n[stopped after {timeout} seconds]"
    return Result(proc.returncode if not timed_out else 124, text, timed_out)


def _run(project_id: int, command: str, network: bool, timeout: int) -> Result:
    if docker_available():
        _ensure_container(project_id)
        name = _container(project_id)
        if network:
            subprocess.run(["docker", "network", "connect", "bridge", name], capture_output=True)
        try:
            return _run_blocking(docker_exec_argv(project_id, command), None, None, timeout)
        finally:
            if network:
                subprocess.run(
                    ["docker", "network", "disconnect", "bridge", name], capture_output=True
                )
    _ensure_venv(project_id)
    env = stripped_env(project_id, network)
    return _run_blocking(command, workspace_path(project_id), env, timeout)


async def run(
    project_id: int, command: str, *, allow_install: bool = False, timeout: int = DEFAULT_TIMEOUT
) -> Result:
    """Run one command for a project. Network only for an install, and only when allowed."""
    install = is_install(command)
    if install and not allow_install:
        return Result(126, "Package installs are only allowed during the build step.")
    timeout = max(1, min(timeout, MAX_TIMEOUT))
    return await asyncio.to_thread(_run, project_id, command.strip(), install, timeout)
