"""Injectable time. Owner: M3 (C-01).

Retention, leases and event ordering all depend on "now", and tests must be able
to move it. Production code takes a `Clock` rather than calling
`datetime.now` directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """A clock the caller advances explicitly. Used by tests, not by the app."""

    def __init__(self, at: datetime):
        if at.tzinfo is None:
            raise ValueError("A fixed clock needs an aware datetime.")
        self._at = at

    def now(self) -> datetime:
        return self._at

    def advance(self, seconds: float) -> None:
        self._at = self._at + timedelta(seconds=seconds)
