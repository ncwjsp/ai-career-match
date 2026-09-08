"""The durable PostgreSQL-backed work queue. Owner: M3 (C-01/C-08).

There is no Redis, Celery or cron in this design: a lightweight worker polls
`work_queue` inside `career_app`. That keeps the service count small and, more
importantly, keeps a queued unit of work in the same database as the results it
produces, so a restart cannot lose work that was already accepted.

Four properties matter, and each is tested in tests/app/test_queue.py:

  - **Idempotency.** `event_id` is the primary key. A job-change event that M2's
    outbox delivers twice inserts once; `enqueue` returns False the second time.
    `processed_events` keeps that guarantee after finished rows are cleaned up.
  - **Leases.** `claim` marks a row `inflight` with an expiry. A worker that
    crashes leaves the lease to expire, and the next claim takes the row back.
    That is the whole of restart recovery: no external scheduler is involved.
  - **Bounded retries.** Each claim counts an attempt. `retry` schedules a
    backoff; past `max_attempts` the row is parked as `failed` with its last
    error, so a poison event cannot spin forever.
  - **Ordering under concurrency.** On PostgreSQL the claim uses
    `FOR UPDATE SKIP LOCKED`, so two workers never take the same row. SQLite
    (tests) has one writer, and the same code path is correct there.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from pydantic import TypeAdapter
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.models import AnalysisRun, DomainEvent, FileRef
from app.core.clock import Clock
from app.core.ids import new_token
from app.core.timeutil import to_storage_utc
from app.db.app.database import supports_skip_locked
from app.db.app.models import ProcessedEventRow, WorkQueueRow

_EVENT = TypeAdapter(DomainEvent)


class SqlProcessedEvents:
    """Durable "already handled" record, kept after queue rows are cleaned up."""

    def __init__(self, factory: sessionmaker[Session], clock: Clock):
        self._factory = factory
        self._clock = clock

    def seen(self, event_id: str) -> bool:
        with self._factory() as session:
            return session.get(ProcessedEventRow, event_id) is not None

    def mark(self, event_id: str, event_type: str) -> None:
        with self._factory() as session:
            if session.get(ProcessedEventRow, event_id) is None:
                session.add(
                    ProcessedEventRow(
                        event_id=event_id,
                        event_type=event_type,
                        processed_at=to_storage_utc(self._clock.now()),
                    )
                )
                session.commit()


class SqlWorkQueue:
    """One named queue over the shared `work_queue` table."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        clock: Clock,
        queue: str,
        *,
        lease_seconds: int = 300,
        max_attempts: int = 5,
        backoff_seconds: int = 30,
        processed: SqlProcessedEvents | None = None,
    ):
        self._factory = factory
        self._clock = clock
        self._queue = queue
        self._lease = timedelta(seconds=lease_seconds)
        self._max_attempts = max_attempts
        self._backoff = backoff_seconds
        self._processed = processed or SqlProcessedEvents(factory, clock)

    def enqueue_payload(self, event_id: str, event_type: str, payload: dict) -> bool:
        """Accept a unit of work once. False means it was already accepted."""
        if self._processed.seen(event_id):
            return False
        now = to_storage_utc(self._clock.now())
        with self._factory() as session:
            if session.get(WorkQueueRow, event_id) is not None:
                return False
            session.add(
                WorkQueueRow(
                    event_id=event_id,
                    queue=self._queue,
                    event_type=event_type,
                    payload=payload,
                    state="pending",
                    attempts=0,
                    max_attempts=self._max_attempts,
                    available_at=now,
                    lease_expires_at=None,
                    lease_owner=None,
                    last_error=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        return True

    def claim_payload(self, owner: str | None = None) -> tuple[str, str, dict] | None:
        """Take the oldest due row, including one whose lease expired."""
        now = to_storage_utc(self._clock.now())
        holder = owner or new_token(12)
        with self._factory() as session:
            query = (
                select(WorkQueueRow)
                .where(WorkQueueRow.queue == self._queue)
                .where(WorkQueueRow.available_at <= now)
                .where(
                    or_(
                        WorkQueueRow.state == "pending",
                        and_(
                            WorkQueueRow.state == "inflight",
                            WorkQueueRow.lease_expires_at <= now,
                        ),
                    )
                )
                .order_by(WorkQueueRow.created_at, WorkQueueRow.event_id)
                .limit(1)
            )
            if supports_skip_locked(session):
                query = query.with_for_update(skip_locked=True)
            row = session.execute(query).scalar_one_or_none()
            if row is None:
                return None
            row.state = "inflight"
            row.attempts += 1
            row.lease_owner = holder
            row.lease_expires_at = to_storage_utc(self._clock.now() + self._lease)
            row.updated_at = now
            claimed = (row.event_id, row.event_type, dict(row.payload))
            session.commit()
            return claimed

    def acknowledge(self, event_id: str) -> None:
        """Finish a unit of work. Recorded durably so a replay is a no-op."""
        with self._factory() as session:
            row = session.get(WorkQueueRow, event_id)
            if row is None:
                return
            row.state = "done"
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = to_storage_utc(self._clock.now())
            session.commit()
            event_type = row.event_type
        self._processed.mark(event_id, event_type)

    def retry(self, event_id: str, error: str | None = None) -> None:
        """Reschedule after a backoff, or park the row once attempts run out."""
        now = self._clock.now()
        with self._factory() as session:
            row = session.get(WorkQueueRow, event_id)
            if row is None:
                return
            row.last_error = error
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = to_storage_utc(now)
            if row.attempts >= row.max_attempts:
                # Parked, not dropped: the row stays readable for an operator.
                row.state = "failed"
            else:
                row.state = "pending"
                row.available_at = to_storage_utc(now + timedelta(seconds=self._backoff))
            session.commit()

    def counts(self) -> dict[str, int]:
        with self._factory() as session:
            rows = session.execute(
                select(WorkQueueRow.state, func.count())
                .where(WorkQueueRow.queue == self._queue)
                .group_by(WorkQueueRow.state)
            ).all()
        return {state: int(count) for state, count in rows}

    def failed_events(self) -> Sequence[str]:
        with self._factory() as session:
            return list(
                session.execute(
                    select(WorkQueueRow.event_id)
                    .where(WorkQueueRow.queue == self._queue)
                    .where(WorkQueueRow.state == "failed")
                    .order_by(WorkQueueRow.event_id)
                )
                .scalars()
                .all()
            )

    def purge_done(self, older_than_seconds: int = 0) -> int:
        """Bounded maintenance. `processed_events` keeps the dedupe guarantee."""
        boundary = to_storage_utc(self._clock.now() - timedelta(seconds=older_than_seconds))
        with self._factory() as session:
            rows = (
                session.execute(
                    select(WorkQueueRow)
                    .where(WorkQueueRow.queue == self._queue)
                    .where(WorkQueueRow.state == "done")
                    .where(WorkQueueRow.updated_at <= boundary)
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.delete(row)
            session.commit()
            return len(rows)


class SqlMatchQueue:
    """`app.contracts.interfaces.MatchQueue` over the durable table."""

    QUEUE = "match"

    def __init__(self, factory: sessionmaker[Session], clock: Clock, **options):
        self._queue = SqlWorkQueue(factory, clock, self.QUEUE, **options)

    def enqueue(self, event: DomainEvent) -> bool:
        return self._queue.enqueue_payload(
            event.event_id, event.event_type, event.model_dump(mode="json")
        )

    def claim(self) -> DomainEvent | None:
        claimed = self._queue.claim_payload()
        if claimed is None:
            return None
        return _EVENT.validate_python(claimed[2])

    def acknowledge(self, event_id: str) -> None:
        self._queue.acknowledge(event_id)

    def retry(self, event_id: str, error: str | None = None) -> None:
        self._queue.retry(event_id, error)

    @property
    def maintenance(self) -> SqlWorkQueue:
        """Counts, parked events and cleanup, for the worker and health checks."""
        return self._queue


class SqlAnalysisQueue:
    """`app.contracts.interfaces.AnalysisQueue`: one resume waiting to be parsed."""

    QUEUE = "analysis"

    def __init__(self, factory: sessionmaker[Session], clock: Clock, **options):
        self._queue = SqlWorkQueue(factory, clock, self.QUEUE, **options)

    def enqueue(self, run: AnalysisRun, file: FileRef) -> None:
        self._queue.enqueue_payload(
            run.analysis_id,
            "analysis.requested",
            {"run": run.model_dump(mode="json"), "file": file.model_dump(mode="json")},
        )

    def claim(self) -> tuple[AnalysisRun, FileRef] | None:
        claimed = self._queue.claim_payload()
        if claimed is None:
            return None
        payload = claimed[2]
        return (
            AnalysisRun.model_validate(payload["run"]),
            FileRef.model_validate(payload["file"]),
        )

    def acknowledge(self, analysis_id: str) -> None:
        self._queue.acknowledge(analysis_id)

    def retry(self, analysis_id: str, error: str | None = None) -> None:
        self._queue.retry(analysis_id, error)

    @property
    def maintenance(self) -> SqlWorkQueue:
        return self._queue
