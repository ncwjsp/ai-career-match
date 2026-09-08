"""SQLAlchemy models for the independent `career_app` database. Owner: M3 (C-01).

Table groups:
  - `sessions` / `candidates`: the retained anonymous session and the candidate
    lifecycle it scopes. `matching_enabled` and `expires_at` on `candidates` are
    the source of truth for whether a new job still matches this person, so
    matching keeps working while the browser is closed and stops at expiry.
  - `resume_uploads` / `candidate_profiles` / `candidate_embeddings`: upload
    metadata pointing at an opaque object key (never the bytes), the versioned
    profile payload and its vector.
  - `analysis_runs`: the upload-to-results lifecycle a browser polls.
  - `work_queue` / `processed_events` / `match_runs`: the durable PostgreSQL
    queue, its cross-restart idempotency record and per-event run state.
  - `match_results` / `recommendation_revisions` / `recommendation_entries` /
    `explanations`: pair scores, immutable published revisions and cached
    grounded explanations.

Contract payloads are stored as JSON documents next to the columns that are
queried or ordered on. The DTO stays the single definition of the shape, and a
contract change does not require a column migration for every field.

Column types are dialect-portable (JSON, DateTime(timezone=True), String) so the
schema runs unchanged on PostgreSQL (deployment) and SQLite (tests). There are
no foreign keys to `career_jobs`: job ids are resolved through M2's repository.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    """One retained anonymous session. Not an account: no credentials are stored."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CandidateRow(Base):
    """Retention state for one candidate. Matching reads this, not the payload."""

    __tablename__ = "candidates"

    candidate_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    current_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matching_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # The active-profile scan for every changed job runs on these two columns.
        Index("ix_candidates_active", "matching_enabled", "expires_at"),
    )


class ResumeUploadRow(Base):
    """Upload metadata. `object_key` points into the S3/local store; bytes never land here."""

    __tablename__ = "resume_uploads"

    resume_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.candidate_id"), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CandidateProfileRow(Base):
    """One immutable version of a parsed profile, as the `CandidateProfile` contract."""

    __tablename__ = "candidate_profiles"

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.candidate_id"), primary_key=True
    )
    profile_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CandidateEmbeddingRow(Base):
    """A persisted resume vector for one profile version and model revision."""

    __tablename__ = "candidate_embeddings"

    candidate_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    profile_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    embedding_version: Mapped[str] = mapped_column(String(100), primary_key=True)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_revision: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["candidate_id", "profile_version"],
            ["candidate_profiles.candidate_id", "candidate_profiles.profile_version"],
        ),
    )


class AnalysisRunRow(Base):
    """The upload-to-results lifecycle the browser polls, as `AnalysisRun`."""

    __tablename__ = "analysis_runs"

    analysis_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.candidate_id"), nullable=False)
    resume_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    """queued | extracting | profiling | matching | ready | failed."""
    corpus_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkQueueRow(Base):
    """The durable PostgreSQL queue. One row per accepted unit of work.

    `event_id` is the primary key, so redelivering a committed job-change event
    is a no-op insert rather than a second match run. A crashed worker leaves an
    `inflight` row whose `lease_expires_at` has passed; the next claim takes it
    back, which is how restart recovery works without an external scheduler.
    """

    __tablename__ = "work_queue"

    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    queue: Mapped[str] = mapped_column(String(30), nullable=False)
    """match | analysis."""
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    """pending | inflight | done | failed."""
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_work_queue_claim", "queue", "state", "available_at"),)


class ProcessedEventRow(Base):
    """Durable record that an event was fully handled, kept after queue cleanup."""

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MatchRunRow(Base):
    """Per-event run state, as `MatchRun`, including its batch checkpoint."""

    __tablename__ = "match_runs"

    run_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    event: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    checkpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_revisions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MatchResultRow(Base):
    """One scored candidate/job pair, keyed by every version that produced it."""

    __tablename__ = "match_results"

    candidate_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    profile_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    job_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    scoring_version: Mapped[str] = mapped_column(String(100), primary_key=True)
    score: Mapped[float] = mapped_column(nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_match_results_ranking", "candidate_id", "profile_version"),)


class RecommendationRevisionRow(Base):
    """One published, immutable ranked set. Pagination binds to `revision`."""

    __tablename__ = "recommendation_revisions"

    candidate_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    refresh_state: Mapped[str] = mapped_column(String(20), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecommendationEntryRow(Base):
    """One ranked row of a published revision, as `Recommendation`."""

    __tablename__ = "recommendation_entries"

    candidate_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(200), nullable=False)
    job_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["candidate_id", "revision"],
            [
                "recommendation_revisions.candidate_id",
                "recommendation_revisions.revision",
            ],
            ondelete="CASCADE",
        ),
    )


class ExplanationRow(Base):
    """A grounded explanation, cached per candidate/revision/job. Never a score input."""

    __tablename__ = "explanations"

    candidate_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    """pending | ready | unavailable."""
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
