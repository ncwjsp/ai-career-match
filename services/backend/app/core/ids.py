"""Opaque identifiers. Owner: M3 (C-01).

Identifiers reach the browser and the object store, so they carry no candidate
data and no guessable ordering. Every value matches the contract `Identifier`
pattern (`^[A-Za-z0-9][A-Za-z0-9_.:-]*$`).
"""

from __future__ import annotations

import secrets
from uuid import uuid4

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def new_id(prefix: str) -> str:
    """A prefixed random identifier, e.g. `cand-3f9a...`."""
    if not prefix or not prefix[0].isalnum():
        raise ValueError("An identifier prefix must start with an alphanumeric character.")
    return f"{prefix}-{uuid4().hex}"


def new_token(length: int = 32) -> str:
    """An unguessable session token. Never derived from candidate data."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
