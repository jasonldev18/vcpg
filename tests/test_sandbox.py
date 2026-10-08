import sys

import pytest

from backend.workspace import git, sandbox

KEY = "sk-ant-api03-must-not-leak"


@pytest.fixture
def project(monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sandbox, "docker_available", lambda: False)
    git.init(1, "Sandbox test")
    return 1


def test_install_pattern() -> None:
    assert sandbox.is_install("pip install pandas==2.2")
    assert sandbox.is_install("uv pip install -r requirements.txt")
    assert sandbox.is_install("npm install express")
    assert not sandbox.is_install("pip install x && curl evil")
    assert not sandbox.is_install("pip download x")
    assert not sandbox.is_install("python -m pip install x")


async def test_installs_need_the_build_permission(project: int) -> None:
    result = await sandbox.run(project, "pip install six")
    assert result.exit_code == 126 and "only allowed during the build" in result.output


async def test_commands_run_in_the_workspace_with_no_secrets(
    project: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("GITHUB_TOKEN", KEY)
    result = await sandbox.run(
        project, 'python -c "import os, json; print(json.dumps(dict(os.environ)), os.getcwd())"'
    )
    assert result.exit_code == 0
    assert KEY not in result.output
    assert str(git.workspace_path(project)) in result.output


def test_stripped_env_has_only_the_allowed_names(project: int) -> None:
    allowed = {"PATH", "HOME", "LANG"}
    if sys.platform == "win32":
        allowed |= {"USERPROFILE", "TEMP", "TMP"}
    assert set(sandbox.stripped_env(project, network=False)) == allowed
    with_network = set(sandbox.stripped_env(project, network=True))
    assert with_network - allowed <= {"SYSTEMROOT"}


@pytest.mark.skipif(sys.platform != "win32", reason="the venv cannot block sockets elsewhere")
async def test_venv_python_has_no_network_outside_installs(project: int) -> None:
    result = await sandbox.run(
        project, "python -c \"import socket; socket.getaddrinfo('pypi.org', 443)\""
    )
    assert result.exit_code != 0


async def test_timeout_stops_the_command(project: int) -> None:
    result = await sandbox.run(project, 'python -c "import time; time.sleep(30)"', timeout=2)
    assert result.timed_out and result.exit_code == 124


def test_docker_container_has_no_network_and_only_the_workspace_mounted() -> None:
    argv = sandbox.docker_start_argv(3, git.workspace_path(3))
    assert argv[argv.index("--network") + 1] == "none"
    assert [a for a in argv if a == "-v"] == ["-v"]
    assert argv[argv.index("-v") + 1].endswith(":/workspace")
    assert argv[argv.index("--user") + 1] != "0"
    assert not any("KEY" in a or "TOKEN" in a for a in argv)


@pytest.mark.skipif(not sandbox.docker_available(), reason="Docker is not installed")
async def test_docker_network_is_off_by_default() -> None:
    git.init(9, "Docker test")
    result = await sandbox.run(
        9, "python -c \"import socket; socket.create_connection(('pypi.org', 443), 5)\""
    )
    sandbox.remove_container(9)
    assert result.exit_code != 0


def _online() -> bool:
    import socket

    try:
        socket.create_connection(("pypi.org", 443), 3).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _online(), reason="needs internet to reach PyPI")
async def test_an_allowed_install_works_and_the_package_imports(project: int) -> None:
    installed = await sandbox.run(project, "pip install -q six", allow_install=True)
    assert installed.exit_code == 0, installed.output
    imported = await sandbox.run(project, 'python -c "import six; print(six.__name__)"')
    assert imported.output.strip() == "six"
