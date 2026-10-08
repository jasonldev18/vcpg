"""The only place that touches the OS keychain. Values never leave memory except to keyring."""

from typing import Literal

import keyring
from keyring.errors import PasswordDeleteError

from backend import redact

SERVICE = "vcpg"
SecretName = Literal["anthropic", "github"]


def get(name: SecretName) -> str | None:
    value = keyring.get_password(SERVICE, name)
    if value:
        redact.remember(value)
    return value


def save(name: SecretName, value: str) -> None:
    redact.remember(value)
    keyring.set_password(SERVICE, name, value)


def remove(name: SecretName) -> None:
    value = keyring.get_password(SERVICE, name)
    try:
        keyring.delete_password(SERVICE, name)
    except PasswordDeleteError:
        return
    if value:
        redact.forget(value)


def last_four(name: SecretName) -> str | None:
    value = get(name)
    return value[-4:] if value else None
