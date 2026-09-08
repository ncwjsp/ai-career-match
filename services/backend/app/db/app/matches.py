"""Pair scores and published recommendation revisions. Owner: M3 (C-01/C-08).

`SqlMatchRepository` stores one row per candidate/profile/job/job-version/
scoring-version tuple, so a rescore under a new model or weight version never
overwrites the score a published revision already cites.

`SqlRecommendationRepository` publishes a *coherent* revision: the revision row
and all of its ranked entries are written in one transaction, and entries are
never edited afterwards. A reader therefore sees either the previous complete
ranking or the new complete ranking, never a half-updated list, and pagination
can bind to a revision number that will not shift underneath it.

Revisions only move forward. Publishing a revision that is already stored is a
no-op when the content matches; publishing an older one is refused, which is how
an out-of-order or replayed job event is prevented from resurrecting a stale
ranking.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.models import MatchResult, Recommendation, RecommendationSet
from app.core.clock import Clock
from app.core.errors import ConflictError
from app.core.timeutil import from_storage_utc, to_storage_utc
from app.db.app.models import (
    MatchResultRow,
    RecommendationEntryRow,
    RecommendationRevisionRow,
)


class SqlMatchRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def upsert(self, result: MatchResult) -> None:
        key = (
            result.candidate_id,
            result.profile_version,
            result.job_id,
            result.job_version,
            result.scoring_version,
        )
        payload = result.model_dump(mode="json")
        with self._factory() as session:
            row = session.get(MatchResultRow, key)
            if row is None:
                session.add(
                    MatchResultRow(
                        candidate_id=result.candidate_id,
                        profile_version=result.profile_version,
                        job_id=result.job_id,
                        job_version=result.job_version,
                        scoring_version=result.scoring_version,
                        score=result.score,
                        payload=payload,
                        matched_at=to_storage_utc(result.matched_at),
                    )
                )
            else:
                # Same versions and same inputs must give the same score; a rerun
                # after a partial failure simply refreshes the row.
                row.score = result.score
                row.payload = payload
                row.matched_at = to_storage_utc(result.matched_at)
            session.commit()

    def list_for_candidate(self, candidate_id: str, profile_version: int) -> Sequence[MatchResult]:
        with self._factory() as session:
            rows = (
                session.execute(
                    select(MatchResultRow)
                    .where(MatchResultRow.candidate_id == candidate_id)
                    .where(MatchResultRow.profile_version == profile_version)
                    # Unrounded score first, then job id: a stable order for ties.
                    .order_by(MatchResultRow.score.desc(), MatchResultRow.job_id)
                )
                .scalars()
                .all()
            )
            return [MatchResult.model_validate(row.payload) for row in rows]

    def remove_job(self, job_id: str) -> None:
        """Drop every stored score for a job that expired or was removed."""
        with self._factory() as session:
            session.execute(delete(MatchResultRow).where(MatchResultRow.job_id == job_id))
            session.commit()

    def count_for_candidate(self, candidate_id: str, profile_version: int) -> int:
        with self._factory() as session:
            return int(
                session.execute(
                    select(func.count())
                    .select_from(MatchResultRow)
                    .where(MatchResultRow.candidate_id == candidate_id)
                    .where(MatchResultRow.profile_version == profile_version)
                ).scalar_one()
            )


class SqlRecommendationRepository:
    def __init__(self, factory: sessionmaker[Session], clock: Clock):
        self._factory = factory
        self._clock = clock

    def latest_revision(self, candidate_id: str) -> int:
        """0 when nothing has been published yet, so the first revision is 1."""
        with self._factory() as session:
            highest = session.execute(
                select(func.max(RecommendationRevisionRow.revision)).where(
                    RecommendationRevisionRow.candidate_id == candidate_id
                )
            ).scalar_one()
            return int(highest or 0)

    def next_revision(self, candidate_id: str) -> int:
        return self.latest_revision(candidate_id) + 1

    def publish(self, result_set: RecommendationSet) -> None:
        """Write the revision and every ranked entry in one transaction."""
        with self._factory() as session:
            existing = session.get(
                RecommendationRevisionRow, (result_set.candidate_id, result_set.revision)
            )
            if existing is not None:
                if existing.result_count != len(result_set.results):
                    raise ConflictError(
                        f"revision {result_set.revision} is already published with "
                        "different content."
                    )
                return  # A replayed publication of the same revision.
            highest = self.latest_revision(result_set.candidate_id)
            if result_set.revision <= highest:
                raise ConflictError(
                    f"revision {result_set.revision} is behind the published "
                    f"revision {highest}; a stale ranking must not be republished."
                )
            session.add(
                RecommendationRevisionRow(
                    candidate_id=result_set.candidate_id,
                    revision=result_set.revision,
                    profile_version=result_set.profile_version,
                    refresh_state=result_set.refresh_state,
                    result_count=len(result_set.results),
                    updated_at=to_storage_utc(result_set.updated_at),
                )
            )
            # Flush the parent first: the entries carry a composite foreign key
            # to it, and the unit of work does not order them for us here.
            session.flush()
            for entry in result_set.results:
                session.add(
                    RecommendationEntryRow(
                        candidate_id=entry.candidate_id,
                        revision=entry.revision,
                        rank=entry.rank,
                        job_id=entry.job_id,
                        job_version=entry.job_version,
                        payload=entry.model_dump(mode="json"),
                    )
                )
            session.commit()

    def get(self, candidate_id: str, revision: int) -> RecommendationSet | None:
        with self._factory() as session:
            row = session.get(RecommendationRevisionRow, (candidate_id, revision))
            if row is None:
                return None
            entries = (
                session.execute(
                    select(RecommendationEntryRow)
                    .where(RecommendationEntryRow.candidate_id == candidate_id)
                    .where(RecommendationEntryRow.revision == revision)
                    .order_by(RecommendationEntryRow.rank)
                )
                .scalars()
                .all()
            )
            return RecommendationSet(
                candidate_id=candidate_id,
                profile_version=row.profile_version,
                revision=revision,
                updated_at=from_storage_utc(row.updated_at),
                refresh_state=row.refresh_state,
                results=[Recommendation.model_validate(e.payload) for e in entries],
                next_cursor=None,
            )

    def latest(self, candidate_id: str) -> RecommendationSet | None:
        revision = self.latest_revision(candidate_id)
        return self.get(candidate_id, revision) if revision else None

    def set_refresh_state(self, candidate_id: str, state: str) -> None:
        """Mark the newest revision pending/failed while a refresh is in flight."""
        revision = self.latest_revision(candidate_id)
        if not revision:
            return
        with self._factory() as session:
            row = session.get(RecommendationRevisionRow, (candidate_id, revision))
            if row is not None:
                row.refresh_state = state
                session.commit()
