"""Retention cleanup. Owner: M3 (C-01).

Bounded maintenance an operator or the worker runs; there is no cron. Expiry
removes the private derivatives of a candidate as well as the original file, so
"expired" does not leave a readable resume behind in the object store.

D06 still has to fix the real retention period. This module implements the
mechanism, not the policy.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.interfaces import ObjectStore
from app.core.clock import Clock
from app.core.timeutil import to_storage_utc
from app.db.app.models import (
    AnalysisRunRow,
    CandidateEmbeddingRow,
    CandidateProfileRow,
    CandidateRow,
    ExplanationRow,
    MatchResultRow,
    RecommendationEntryRow,
    RecommendationRevisionRow,
    ResumeUploadRow,
    SessionRow,
)


class RetentionCleaner:
    def __init__(self, factory: sessionmaker[Session], store: ObjectStore, clock: Clock):
        self._factory = factory
        self._store = store
        self._clock = clock

    def expired_candidates(self, at: datetime | None = None, limit: int = 100) -> Sequence[str]:
        boundary = to_storage_utc(at or self._clock.now())
        with self._factory() as session:
            return list(
                session.execute(
                    select(CandidateRow.candidate_id)
                    .where(CandidateRow.expires_at <= boundary)
                    .order_by(CandidateRow.candidate_id)
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def purge(self, candidate_id: str) -> None:
        """Remove one candidate's stored file and every derivative of it."""
        from app.contracts.models import FileRef

        with self._factory() as session:
            uploads = (
                session.execute(
                    select(ResumeUploadRow).where(ResumeUploadRow.candidate_id == candidate_id)
                )
                .scalars()
                .all()
            )
            files = [FileRef(object_key=u.object_key, media_type=u.media_type) for u in uploads]

        # Delete the bytes first: a crash then leaves rows pointing at an absent
        # object, which is recoverable, rather than an orphaned readable resume.
        for file in files:
            self._store.delete(file)

        with self._factory() as session:
            session.execute(
                delete(RecommendationEntryRow).where(
                    RecommendationEntryRow.candidate_id == candidate_id
                )
            )
            for table in (
                RecommendationRevisionRow,
                ExplanationRow,
                MatchResultRow,
                CandidateEmbeddingRow,
                CandidateProfileRow,
                AnalysisRunRow,
                ResumeUploadRow,
                SessionRow,
            ):
                session.execute(delete(table).where(table.candidate_id == candidate_id))
            session.execute(delete(CandidateRow).where(CandidateRow.candidate_id == candidate_id))
            session.commit()

    def run_once(self, at: datetime | None = None, limit: int = 100) -> int:
        """One bounded sweep. Returns how many candidates were removed."""
        expired = self.expired_candidates(at, limit)
        for candidate_id in expired:
            self.purge(candidate_id)
        return len(expired)
