"""Core access: key status, save, test and remove. Keys are never returned (SECURITY section 2)."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend import secrets
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
