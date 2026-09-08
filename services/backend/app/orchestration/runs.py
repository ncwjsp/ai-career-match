"""Per-event match-run state. Owner: M3 (C-08).

One row per accepted event, as the `MatchRun` contract. It records the batch
`checkpoint` a long job-change run reached and which revision it published for
each candidate, so a worker that restarts mid-run resumes after the last
completed batch instead of rescoring every retained candidate again.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.contracts.models import DomainEvent, ErrorDetail, MatchRun
from app.core.clock import Clock
from app.core.ids import new_id
from app.core.timeutil import from_storage_utc, to_storage_utc
from app.db.app.models import MatchRunRow


class SqlMatchRunRepository:
    def __init__(self, factory: sessionmaker[Session], clock: Clock):
        self._factory = factory
        self._clock = clock

    def start(self, event: DomainEvent) -> MatchRun:
        """Reuse the existing run for a redelivered event so its checkpoint survives."""
        now = to_storage_utc(self._clock.now())
        with self._factory() as session:
            row = _by_event(session, event.event_id)
            if row is None:
                row = MatchRunRow(
                    run_id=new_id("run"),
                    event_id=event.event_id,
                    event=event.model_dump(mode="json"),
                    state="running",
                    checkpoint=None,
                    error=None,
                    published_revisions={},
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.state = "running"
                row.error = None
                row.updated_at = now
            session.commit()
            return _to_contract(row)

    def checkpoint(self, run_id: str, checkpoint: str | None) -> None:
        with self._factory() as session:
            row = session.get(MatchRunRow, run_id)
            if row is not None:
                row.checkpoint = checkpoint
                row.updated_at = to_storage_utc(self._clock.now())
                session.commit()

    def record_revision(self, run_id: str, candidate_id: str, revision: int) -> None:
        with self._factory() as session:
            row = session.get(MatchRunRow, run_id)
            if row is not None:
                published = dict(row.published_revisions)
                published[candidate_id] = revision
                row.published_revisions = published
                row.updated_at = to_storage_utc(self._clock.now())
                session.commit()

    def finish(self, run_id: str) -> None:
        self._set_state(run_id, "ready")

    def fail(self, run_id: str, error: ErrorDetail) -> None:
        self._set_state(run_id, "failed", error)

    def get(self, run_id: str) -> MatchRun | None:
        with self._factory() as session:
            row = session.get(MatchRunRow, run_id)
            return _to_contract(row) if row is not None else None

    def by_event(self, event_id: str) -> MatchRun | None:
        with self._factory() as session:
            row = _by_event(session, event_id)
            return _to_contract(row) if row is not None else None

    def _set_state(self, run_id: str, state: str, error: ErrorDetail | None = None) -> None:
        with self._factory() as session:
            row = session.get(MatchRunRow, run_id)
            if row is not None:
                row.state = state
                row.error = error.model_dump(mode="json") if error else None
                if state == "ready":
                    row.checkpoint = None
                row.updated_at = to_storage_utc(self._clock.now())
                session.commit()


def _by_event(session: Session, event_id: str) -> MatchRunRow | None:
    return session.query(MatchRunRow).filter(MatchRunRow.event_id == event_id).one_or_none()


def _to_contract(row: MatchRunRow) -> MatchRun:
    return MatchRun(
        run_id=row.run_id,
        event=row.event,
        state=row.state,
        checkpoint=row.checkpoint,
        created_at=from_storage_utc(row.created_at),
        updated_at=from_storage_utc(row.updated_at),
        error=ErrorDetail.model_validate(row.error) if row.error else None,
        published_revisions=dict(row.published_revisions),
    )
