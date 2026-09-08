"""Timezone normalization for every `career_app` read/write path. Owner: M3.

SQLite (used in tests) drops the offset on a `DateTime(timezone=True)` column:
`2026-09-05T05:00:00+05:00` reads back as the naive wall clock
`2026-09-05T05:00:00`, a different instant once reattached as UTC. PostgreSQL
stores the instant correctly. Normalizing to UTC on the way in keeps both
dialects consistent. `app/db/jobs/timeutil.py` is M2's identical copy; collapsing
the two belongs in a shared PR, not in a feature branch that edits their folder.
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
