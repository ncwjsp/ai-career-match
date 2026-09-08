"""Job source registration and manual import-run/check metadata. Owner: M2 (B-09).

These are plain repositories for tables B-01 (source register) and B-02 (import
service) will drive; they are not yet canonical contracts (`app/contracts/`),
so the return shape here is this module's own dataclasses, not shared DTOs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.jobs.models import JobImportRunRow, JobRawSnapshotRow, JobSourceRow
from app.db.jobs.timeutil import from_storage_utc, to_storage_utc


@dataclass(frozen=True)
class JobSource:
    source_id: str
    name: str
    base_url: str
    source_type: str
    permitted: bool
    permitted_notes: str | None
    rate_limit_notes: str | None
    checked_at: datetime | None


@dataclass(frozen=True)
class JobImportRun:
    run_id: str
    source_id: str | None
    source_url: str
    job_id: str | None
    status: str
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


def _source_from_row(row: JobSourceRow) -> JobSource:
    return JobSource(
        source_id=row.source_id,
        name=row.name,
        base_url=row.base_url,
        source_type=row.source_type,
        permitted=row.permitted,
        permitted_notes=row.permitted_notes,
        rate_limit_notes=row.rate_limit_notes,
        checked_at=from_storage_utc(row.checked_at),
    )


def _run_from_row(row: JobImportRunRow) -> JobImportRun:
    return JobImportRun(
        run_id=row.run_id,
        source_id=row.source_id,
        source_url=row.source_url,
        job_id=row.job_id,
        status=row.status,
        error_message=row.error_message,
        started_at=from_storage_utc(row.started_at),
        finished_at=from_storage_utc(row.finished_at),
    )


class SqlJobSourceRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def register(
        self,
        source_id: str,
        name: str,
        base_url: str,
        source_type: str,
        permitted: bool,
        permitted_notes: str | None = None,
        rate_limit_notes: str | None = None,
    ) -> JobSource:
        now = datetime.now(UTC)
        with self._factory() as session:
            row = session.get(JobSourceRow, source_id)
            if row is None:
                row = JobSourceRow(source_id=source_id, created_at=now)
                session.add(row)
            row.name = name
            row.base_url = base_url
            row.source_type = source_type
            row.permitted = permitted
            row.permitted_notes = permitted_notes
            row.rate_limit_notes = rate_limit_notes
            row.updated_at = now
            session.commit()
            return _source_from_row(row)

    def mark_checked(self, source_id: str, at: datetime) -> None:
        with self._factory() as session:
            row = session.get(JobSourceRow, source_id)
            if row is not None:
                row.checked_at = to_storage_utc(at)
                row.updated_at = to_storage_utc(at)
                session.commit()

    def get(self, source_id: str) -> JobSource | None:
        with self._factory() as session:
            row = session.get(JobSourceRow, source_id)
            return _source_from_row(row) if row is not None else None

    def list(self) -> list[JobSource]:
        with self._factory() as session:
            rows = session.execute(select(JobSourceRow).order_by(JobSourceRow.source_id)).scalars()
            return [_source_from_row(row) for row in rows]


class SqlJobImportRunRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def start(self, run_id: str, source_url: str, source_id: str | None = None) -> JobImportRun:
        now = datetime.now(UTC)
        with self._factory() as session:
            row = JobImportRunRow(
                run_id=run_id,
                source_id=source_id,
                source_url=source_url,
                job_id=None,
                status="queued",
                error_message=None,
                started_at=now,
                finished_at=None,
            )
            session.add(row)
            session.commit()
            return _run_from_row(row)

    def complete(
        self,
        run_id: str,
        status: str,
        job_id: str | None = None,
        error_message: str | None = None,
    ) -> JobImportRun:
        if status not in ("success", "unchanged", "failed"):
            raise ValueError(f"Unexpected terminal import status: {status!r}")
        with self._factory() as session:
            row = session.get(JobImportRunRow, run_id)
            if row is None:
                raise LookupError(f"No import run {run_id!r} to complete.")
            row.status = status
            row.job_id = job_id
            row.error_message = error_message
            row.finished_at = datetime.now(UTC)
            session.commit()
            return _run_from_row(row)

    def get(self, run_id: str) -> JobImportRun | None:
        with self._factory() as session:
            row = session.get(JobImportRunRow, run_id)
            return _run_from_row(row) if row is not None else None

    def last_successful_check(self, source_url: str) -> datetime | None:
        """The most recent successful or unchanged check for a URL (freshness display)."""
        with self._factory() as session:
            row = session.execute(
                select(JobImportRunRow)
                .where(JobImportRunRow.source_url == source_url)
                .where(JobImportRunRow.status.in_(("success", "unchanged")))
                .order_by(JobImportRunRow.finished_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            return from_storage_utc(row.finished_at) if row is not None else None


class SqlJobRawSnapshotRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def save(
        self,
        snapshot_id: str,
        run_id: str,
        source_url: str,
        fetched_at: datetime,
        media_type: str,
        content_hash: str,
        raw_content: str,
    ) -> None:
        with self._factory() as session:
            session.add(
                JobRawSnapshotRow(
                    snapshot_id=snapshot_id,
                    run_id=run_id,
                    source_url=source_url,
                    fetched_at=to_storage_utc(fetched_at),
                    media_type=media_type,
                    content_hash=content_hash,
                    raw_content=raw_content,
                )
            )
            session.commit()

    def get(self, snapshot_id: str) -> str | None:
        with self._factory() as session:
            row = session.get(JobRawSnapshotRow, snapshot_id)
            return row.raw_content if row is not None else None
