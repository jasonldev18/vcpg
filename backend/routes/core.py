"""Core access: key status, save, test and remove. Keys are never returned (SECURITY section 2)."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend import secrets
from backend.audit import github
from backend.llm import client

router = APIRouter(prefix="/api/core/anthropic")


class Key(BaseModel):
    key: str = Field(min_length=10, max_length=500)


class KeyStatus(BaseModel):
    saved: bool
    last4: str | None


def _status() -> KeyStatus:
    last4 = secrets.last_four("anthropic")
    return KeyStatus(saved=last4 is not None, last4=last4)


@router.get("")
def status() -> KeyStatus:
    return _status()


@router.put("")
async def save(body: Key) -> KeyStatus:
    """Tested before saving, so a bad paste never replaces a working key."""
    await client.check_key(body.key.strip())
    secrets.save("anthropic", body.key.strip())
    return _status()


@router.post("/test")
async def test() -> KeyStatus:
    key = secrets.get("anthropic")
    if key:
        await client.check_key(key)
    return _status()


@router.delete("")
def remove() -> KeyStatus:
    secrets.remove("anthropic")
    return _status()


github_router = APIRouter(prefix="/api/core/github")


class Token(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class TokenStatus(BaseModel):
    saved: bool
    last4: str | None
    found: list[str] = []
    problems: list[str] = []


def _github_status(check: github.TokenCheck | None = None) -> TokenStatus:
    last4 = secrets.last_four("github")
    return TokenStatus(
        saved=last4 is not None,
        last4=last4,
        found=check.found if check else [],
        problems=check.problems if check else [],
    )


@github_router.get("")
def github_status() -> TokenStatus:
    return _github_status()


@github_router.put("")
async def save_github(body: Token) -> TokenStatus:
    """Checked on save: a token broader than Contents and Pull requests on vcpg is refused."""
    check = await github.check_token(body.token.strip())
    if check.ok:
        secrets.save("github", body.token.strip())
    return _github_status(check)


@github_router.post("/test")
async def test_github() -> TokenStatus:
    token = secrets.get("github")
    return _github_status(await github.check_token(token) if token else None)


@github_router.delete("")
def remove_github() -> TokenStatus:
    secrets.remove("github")
    return _github_status()
