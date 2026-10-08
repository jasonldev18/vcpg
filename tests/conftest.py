from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Never touch the real ~/.vcpg from tests."""
    monkeypatch.setenv("VCPG_HOME", str(tmp_path))
    return tmp_path
