import io
import logging
from collections.abc import Iterator

import pytest

from backend import secrets
from backend.redact import MASK, RedactFilter, install, redact

FAKE_KEY = "sk-ant-api03-FAKEfakeFAKEfake_1234-abcd"
STORED = "plain-looking-token-9f8e7d"  # no known prefix: only caught because it is stored


@pytest.fixture
def log() -> Iterator[tuple[logging.Logger, io.StringIO]]:
    out = io.StringIO()
    handler = logging.StreamHandler(out)
    handler.addFilter(RedactFilter())
    logger = logging.getLogger("vcpg.test")
    logger.addHandler(handler)
    yield logger, out
    logger.removeHandler(handler)


def test_log_line_with_fake_key_and_stored_value_is_redacted(
    log: tuple[logging.Logger, io.StringIO],
) -> None:
    logger, out = log
    secrets.save("github", STORED)
    logger.warning("calling with %s and %s", FAKE_KEY, STORED)
    line = out.getvalue()
    assert FAKE_KEY not in line
    assert STORED not in line
    assert line.count(MASK) == 2


def test_exception_text_is_redacted(log: tuple[logging.Logger, io.StringIO]) -> None:
    logger, out = log
    secrets.save("anthropic", STORED)
    try:
        raise RuntimeError(f"auth failed for {STORED} / {FAKE_KEY}")
    except RuntimeError:
        logger.exception("request failed")
    assert STORED not in out.getvalue()
    assert FAKE_KEY not in out.getvalue()
    assert "RuntimeError" in out.getvalue()


@pytest.mark.parametrize("prefix", ["sk-ant-", "github_pat_", "ghp_", "gho_", "ghs_"])
def test_every_known_prefix_is_masked(prefix: str) -> None:
    assert redact(f"token={prefix}Abc123_xyz end") == f"token={MASK} end"


def test_install_attaches_filter_to_existing_handlers() -> None:
    handler = logging.StreamHandler(io.StringIO())
    logger = logging.getLogger("uvicorn.fake")
    logger.addHandler(handler)
    install()
    install()
    logger.removeHandler(handler)
    assert sum(isinstance(f, RedactFilter) for f in handler.filters) == 1


def test_secret_round_trip_returns_only_last_four() -> None:
    assert secrets.last_four("anthropic") is None
    secrets.save("anthropic", FAKE_KEY)
    assert secrets.last_four("anthropic") == "abcd"
    secrets.remove("anthropic")
    secrets.remove("anthropic")
    assert secrets.get("anthropic") is None
    assert redact(FAKE_KEY) == MASK  # still caught by its prefix after removal
