import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def vcpg_home() -> Path:
    return Path(os.environ.get("VCPG_HOME", Path.home() / ".vcpg"))
