"""Retained anonymous sessions and candidate scope. Owner: M3 (C-01).

A session is an unguessable token bound to exactly one `candidate_id`. It is not
an account: no credential, name or email is stored, and the token is the only
thing that authorizes reading that candidate's data. `require_candidate` is the
single place that turns a token into a candidate id, so a missing, expired or
foreign token cannot reach a repository at all.

Expiry stops *access*. It does not by itself stop matching: `candidates.expires_at`
governs that, and retention cleanup (`app.orchestration.retention`) is what
removes the data. D06 still has to fix the real durations.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.errors import Forbidden
from app.core.ids import new_id, new_token
from app.core.timeutil import from_storage_utc, to_storage_utc
from app.db.app.models import CandidateRow, SessionRow


class SqlSessionStore:
    def __init__(self, factory: sessionmaker[Session], clock: Clock, retention_days: int = 30):
        self._factory = factory
        self._clock = clock
        self._retention = timedelta(days=retention_days)

    def start(self) -> tuple[str, str]:
        """Create a candidate and its session. Returns `(session_id, candidate_id)`."""
        now = self._clock.now()
        expires_at = now + self._retention
        session_id = new_token()
        candidate_id = new_id("cand")
        with self._factory() as session:
            session.add(
                CandidateRow(
                    candidate_id=candidate_id,
                    current_profile_version=None,
                    matching_enabled=True,
                    expires_at=to_storage_utc(expires_at),
                    created_at=to_storage_utc(now),
                    updated_at=to_storage_utc(now),
                )
            )
            session.add(
                SessionRow(
                    session_id=session_id,
                    candidate_id=candidate_id,
                    created_at=to_storage_utc(now),
                    last_seen_at=to_storage_utc(now),
                    expires_at=to_storage_utc(expires_at),
                )
            )
            session.commit()
        return session_id, candidate_id

    def resolve(self, session_id: str | None) -> str | None:
        """The candidate this token may read, or None. Also refreshes `last_seen_at`."""
        if not session_id:
            return None
        now = self._clock.now()
        with self._factory() as session:
            row = session.get(SessionRow, session_id)
            if row is None:
                return None
            expires_at = from_storage_utc(row.expires_at)
            if expires_at is not None and expires_at <= now:
                return None
            row.last_seen_at = to_storage_utc(now)
            session.commit()
            return row.candidate_id

    def require_candidate(self, session_id: str | None, candidate_id: str) -> str:
        """Authorize one candidate-scoped read. Raises rather than returning data."""
        resolved = self.resolve(session_id)
        if resolved is None or resolved != candidate_id:
            # One message for "unknown", "expired" and "someone else's": a caller
            # must not be able to probe which candidate ids exist.
            raise Forbidden("This session may not access that candidate.")
        return resolved

    def expires_at(self, session_id: str) -> datetime | None:
        with self._factory() as session:
            row = session.get(SessionRow, session_id)
            return from_storage_utc(row.expires_at) if row else None
