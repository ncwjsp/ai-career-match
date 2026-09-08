"""Timezone normalization shared by `career_jobs` read/write paths.

SQLite (used in tests) silently drops timezone offsets on `DateTime(timezone=True)`
columns: a value written as `2026-09-05T05:00:00+05:00` reads back as the naive
wall clock `2026-09-05T05:00:00`, a different instant once re-attached as UTC.
PostgreSQL (deployment) stores the instant correctly. Normalizing every
timestamp to UTC before it is written keeps both dialects consistent and makes
the naive value read back from SQLite reattach to the same instant that went in.
"""

from __future__ import annotations

from datetime import UTC, datetime


def to_storage_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC before writing it to a DateTime column."""
    return value.astimezone(UTC)


def from_storage_utc(value: datetime | None) -> datetime | None:
    """Reattach/normalize UTC after reading a DateTime column back."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
