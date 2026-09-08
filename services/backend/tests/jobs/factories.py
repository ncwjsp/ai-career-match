"""Builders for `career_jobs` test fixtures. Owner: M2 (B-09)."""

from datetime import UTC, datetime

from app.contracts.models import (
    EmbeddingRecord,
    EvidenceRef,
    JobChangeEvent,
    JobPosting,
    JobRequirement,
)

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def evidence(excerpt: str = "Required skills: Python.") -> EvidenceRef:
    return EvidenceRef(
        document_id="job-1",
        document_version=1,
        chunk_id="requirements",
        page=1,
        section="requirements",
        start=0,
        end=len(excerpt),
        excerpt=excerpt,
    )


def requirement(skill: str = "Python", required: bool = True) -> JobRequirement:
    return JobRequirement(skill=skill, required=required, evidence=[evidence()])


def make_job(
    job_id: str = "job-1",
    content_version: int = 1,
    *,
    title: str = "NLP engineer",
    active: bool = True,
    expires_at: datetime | None = None,
    fetched_at: datetime = NOW,
) -> JobPosting:
    return JobPosting(
        job_id=job_id,
        source_id="fixture-source",
        source_url="https://jobs.example.test/job-1",
        content_version=content_version,
        title=title,
        company="Example Labs",
        description="Required skills: Python.",
        summary=None,
        requirements=[requirement()],
        other_requirements=[],
        evidence=[evidence()],
        language="en",
        fetched_at=fetched_at,
        last_seen_at=fetched_at,
        posted_at=fetched_at,
        expires_at=expires_at,
        active=active,
        data_origin="fixture",
    )


def make_event(
    job_id: str = "job-1",
    job_version: int = 1,
    *,
    event_id: str = "event-1",
    event_type: str = "job.created",
    occurred_at: datetime = NOW,
) -> JobChangeEvent:
    return JobChangeEvent(
        event_id=event_id,
        event_type=event_type,
        job_id=job_id,
        job_version=job_version,
        occurred_at=occurred_at,
        content_ref=f"{job_id}@{job_version}",
    )


def make_embedding(
    job_id: str = "job-1",
    content_version: int = 1,
    *,
    embedding_version: str = "job-embed-v1",
    dimensions: int = 4,
) -> EmbeddingRecord:
    return EmbeddingRecord(
        entity_id=job_id,
        entity_version=content_version,
        vector=[0.1] * dimensions,
        model_id="fixture-encoder",
        model_revision="rev-1",
        dimensions=dimensions,
        preprocessing_version="prep-v1",
        embedding_version=embedding_version,
    )
