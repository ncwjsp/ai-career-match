"""SQLAlchemy models for the independent `career_jobs` database. Owner: M2 (B-09).

Table groups:
  - `job_sources` / `job_import_runs` / `job_raw_snapshots`: source registration and
    manual-import provenance (consumed by B-01/B-02).
  - `jobs` / `job_versions`: the canonical job entity and its immutable content
    versions, matching the `JobPosting` contract.
  - `job_embeddings`: persisted job vectors keyed by job version + embedding model
    revision (consumed by B-03).
  - `job_change_events`: the transactional outbox. A row is committed in the same
    transaction as the `job_versions` row it describes; `save_with_event` in
    `repository.py` is the only writer.

Column types are kept dialect-portable (JSON, DateTime(timezone=True), String
identifiers) so the schema runs unchanged on PostgreSQL (deployment) and SQLite
(tests, see tests/jobs/conftest.py) rather than relying on Postgres-only types.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JobSourceRow(Base):
    """A registered, evaluated job-URL source (B-01 register)."""

    __tablename__ = "job_sources"

    source_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    permitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permitted_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JobImportRunRow(Base):
    """One manual import/refresh attempt for a single job URL (B-02 consumer)."""

    __tablename__ = "job_import_runs"

    run_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_sources.source_id"), nullable=True
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    """One of: queued, success, unchanged, failed."""
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobRawSnapshotRow(Base):
    """The raw fetched response for one import run, kept for reprocessing/audit."""

    __tablename__ = "job_raw_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("job_import_runs.run_id"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)


class JobRow(Base):
    """The canonical job entity: one row per `job_id`, pointing at its latest version."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    versions: Mapped[list[JobVersionRow]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobVersionRow(Base):
    """One immutable content version of a job, matching the `JobPosting` contract."""

    __tablename__ = "job_versions"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.job_id"), primary_key=True)
    content_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[list] = mapped_column(JSON, nullable=False)
    other_requirements: Mapped[list] = mapped_column(JSON, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    """A change-detection hint for B-02's ingestion decision, not a uniqueness rule:
    a later version legitimately repeats an earlier version's hash (e.g. closing a
    job flips `active` without changing its text)."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped[JobRow] = relationship(back_populates="versions")


class JobEmbeddingRow(Base):
    """A persisted job vector for one content version and embedding model revision."""

    __tablename__ = "job_embeddings"

    job_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    content_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    embedding_version: Mapped[str] = mapped_column(String(100), primary_key=True)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_revision: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "content_version"],
            ["job_versions.job_id", "job_versions.content_version"],
        ),
    )


class JobChangeEventRow(Base):
    """The transactional outbox: one row per `JobChangeEvent`, written with its version."""

    __tablename__ = "job_change_events"

    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    job_id: Mapped[str] = mapped_column(String(200), nullable=False)
    job_version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
