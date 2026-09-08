"""Analysis run lifecycle. Owner: M3 (C-01/C-05).

One row per upload, as the `AnalysisRun` contract: it is what the browser polls
between "file accepted" and "ranked jobs are ready", and what a restarted worker
reads to know a run was already in flight. State only moves forward through
queued -> extracting -> profiling -> matching -> ready, or sideways to failed;
a stale task cannot drag a finished run backwards.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.contracts.models import AnalysisRun, ErrorDetail
from app.core.clock import Clock
from app.core.errors import ConflictError, NotFound
from app.core.timeutil import from_storage_utc, to_storage_utc
from app.db.app.models import AnalysisRunRow

ORDER = ["queued", "extracting", "profiling", "matching", "ready"]


class SqlAnalysisRepository:
    def __init__(self, factory: sessionmaker[Session], clock: Clock):
        self._factory = factory
        self._clock = clock

    def create(self, analysis_id: str, candidate_id: str, resume_id: str) -> AnalysisRun:
        now = self._clock.now()
        with self._factory() as session:
            session.add(
                AnalysisRunRow(
                    analysis_id=analysis_id,
                    candidate_id=candidate_id,
                    resume_id=resume_id,
                    state="queued",
                    corpus_snapshot=None,
                    warnings=[],
                    error=None,
                    result_count=0,
                    created_at=to_storage_utc(now),
                    updated_at=to_storage_utc(now),
                )
            )
            session.commit()
        return self.get(analysis_id)

    def get(self, analysis_id: str) -> AnalysisRun | None:
        with self._factory() as session:
            row = session.get(AnalysisRunRow, analysis_id)
            return _to_contract(row) if row is not None else None

    def advance(
        self,
        analysis_id: str,
        state: str,
        *,
        result_count: int | None = None,
        corpus_snapshot: str | None = None,
        warnings: list[str] | None = None,
    ) -> AnalysisRun:
        with self._factory() as session:
            row = _require(session, analysis_id)
            if row.state == "failed":
                raise ConflictError("A failed analysis cannot be advanced.")
            if state not in ORDER:
                raise ValueError(f"Unknown analysis state {state!r}.")
            if ORDER.index(state) < ORDER.index(row.state):
                # A late task from an earlier stage must not undo later progress.
                return _to_contract(row)
            row.state = state
            if result_count is not None:
                row.result_count = result_count
            if corpus_snapshot is not None:
                row.corpus_snapshot = corpus_snapshot
            if warnings:
                row.warnings = list(row.warnings) + warnings
            row.updated_at = to_storage_utc(self._clock.now())
            session.commit()
            return _to_contract(row)

    def fail(self, analysis_id: str, error: ErrorDetail) -> AnalysisRun:
        with self._factory() as session:
            row = _require(session, analysis_id)
            row.state = "failed"
            row.error = error.model_dump(mode="json")
            row.updated_at = to_storage_utc(self._clock.now())
            session.commit()
            return _to_contract(row)


def _require(session: Session, analysis_id: str) -> AnalysisRunRow:
    row = session.get(AnalysisRunRow, analysis_id)
    if row is None:
        raise NotFound("Unknown analysis.")
    return row


def _to_contract(row: AnalysisRunRow) -> AnalysisRun:
    return AnalysisRun(
        analysis_id=row.analysis_id,
        candidate_id=row.candidate_id,
        resume_id=row.resume_id,
        state=row.state,
        created_at=from_storage_utc(row.created_at),
        updated_at=from_storage_utc(row.updated_at),
        corpus_snapshot=row.corpus_snapshot,
        warnings=list(row.warnings),
        error=ErrorDetail.model_validate(row.error) if row.error else None,
        result_count=row.result_count,
    )
