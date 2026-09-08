"""PostgreSQL-backed `JobRepository`/`JobEventOutbox` for `career_jobs`. Owner: M2 (B-09).

`SqlJobRepository` implements both `app.contracts.interfaces.JobRepository` and
`JobEventOutbox` against the same outbox table, mirroring how
`app.testing.memory.MemoryJobs` covers both protocols for the in-memory double.
`save_with_event` is the only writer of `job_versions`/`jobs`/`job_change_events`
and commits all three in one transaction: a failure partway through leaves no
event row behind (see tests/jobs/test_repository.py).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.models import JobChangeEvent, JobPosting
from app.db.jobs.mapping import (
    content_hash,
    event_row_fields,
    event_row_to_event,
    job_version_fields,
    version_row_to_posting,
)
from app.db.jobs.models import JobChangeEventRow, JobRow, JobVersionRow


class JobEventConflict(ValueError):
    """Raised when an `event_id` is reused for a different event body."""


class JobVersionConflict(ValueError):
    """Raised when a `content_version` is reused for different job content."""


def _latest_version_subquery():
    return (
        select(
            JobVersionRow.job_id,
            func.max(JobVersionRow.content_version).label("content_version"),
        )
        .group_by(JobVersionRow.job_id)
        .subquery()
    )


class SqlJobRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def get(self, job_id: str, version: int | None = None) -> JobPosting | None:
        with self._factory() as session:
            if version is not None:
                row = session.get(JobVersionRow, (job_id, version))
            else:
                latest = _latest_version_subquery()
                row = session.execute(
                    select(JobVersionRow)
                    .join(
                        latest,
                        (JobVersionRow.job_id == latest.c.job_id)
                        & (JobVersionRow.content_version == latest.c.content_version),
                    )
                    .where(JobVersionRow.job_id == job_id)
                ).scalar_one_or_none()
            return version_row_to_posting(row) if row is not None else None

    def list_active(self, at: datetime) -> Sequence[JobPosting]:
        latest = _latest_version_subquery()
        with self._factory() as session:
            rows = (
                session.execute(
                    select(JobVersionRow)
                    .join(
                        latest,
                        (JobVersionRow.job_id == latest.c.job_id)
                        & (JobVersionRow.content_version == latest.c.content_version),
                    )
                    .where(JobVersionRow.active.is_(True))
                    .where((JobVersionRow.expires_at.is_(None)) | (JobVersionRow.expires_at > at))
                    .order_by(JobVersionRow.job_id)
                )
                .scalars()
                .all()
            )
            return [version_row_to_posting(row) for row in rows]

    def save_with_event(self, job: JobPosting, event: JobChangeEvent) -> None:
        if (job.job_id, job.content_version) != (event.job_id, event.job_version):
            raise ValueError("Job and event versions must match.")
        now = datetime.now(UTC)
        with self._factory() as session:
            existing_event = session.get(JobChangeEventRow, event.event_id)
            if existing_event is not None:
                if event_row_to_event(existing_event) != event:
                    raise JobEventConflict(
                        f"event_id {event.event_id!r} already identifies a different event."
                    )
                return  # Already committed by a prior delivery of the same event.

            version_fields = job_version_fields(job)
            existing_version = session.get(JobVersionRow, (job.job_id, job.content_version))
            if existing_version is not None:
                if existing_version.content_hash != version_fields["content_hash"]:
                    raise JobVersionConflict(
                        f"content_version {job.content_version} for job {job.job_id!r} "
                        "already describes different content."
                    )
            else:
                session.add(JobVersionRow(**version_fields, created_at=now))

            job_row = session.get(JobRow, job.job_id)
            if job_row is None:
                session.add(
                    JobRow(
                        job_id=job.job_id,
                        current_version=job.content_version,
                        active=job.active,
                        canonical_url=str(job.source_url),
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                job_row.current_version = max(job_row.current_version, job.content_version)
                job_row.active = job.active
                job_row.updated_at = now

            session.add(JobChangeEventRow(**event_row_fields(event, created_at=now)))
            session.commit()

    def pending(self, limit: int = 100) -> Sequence[JobChangeEvent]:
        with self._factory() as session:
            rows = (
                session.execute(
                    select(JobChangeEventRow)
                    .where(JobChangeEventRow.acknowledged_at.is_(None))
                    .order_by(JobChangeEventRow.created_at, JobChangeEventRow.event_id)
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [event_row_to_event(row) for row in rows]

    def acknowledge(self, event_id: str) -> None:
        with self._factory() as session:
            row = session.get(JobChangeEventRow, event_id)
            if row is not None:
                row.acknowledged_at = datetime.now(UTC)
                session.commit()


__all__ = ["SqlJobRepository", "JobEventConflict", "JobVersionConflict", "content_hash"]
