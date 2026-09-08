"""Builders for `career_app` test fixtures. Owner: M3 (C-01)."""

from datetime import UTC, datetime, timedelta

from app.contracts.models import (
    CandidateProfile,
    EmbeddingRecord,
    EvidenceRef,
    JobChangeEvent,
    ProfileReadyEvent,
    SkillEvidence,
)

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def evidence(document_id: str = "resume-1", excerpt: str = "Python and PyTorch.") -> EvidenceRef:
    return EvidenceRef(
        document_id=document_id,
        document_version=1,
        chunk_id="skills",
        page=1,
        section="skills",
        start=0,
        end=len(excerpt),
        excerpt=excerpt,
    )


def make_profile(
    candidate_id: str = "cand-1",
    profile_version: int = 1,
    *,
    summary: str | None = "Python engineer.",
    matching_enabled: bool = True,
    expires_at: datetime | None = None,
) -> CandidateProfile:
    return CandidateProfile(
        candidate_id=candidate_id,
        resume_id=f"resume-{candidate_id}",
        profile_version=profile_version,
        language="en",
        summary=summary,
        skills=[SkillEvidence(name="Python", evidence=[evidence()])],
        education=[],
        job_titles=["ML engineer"],
        organizations=["Example Labs"],
        experience=[],
        estimated_experience_years=3.0,
        projects=[],
        evidence=[evidence()],
        extraction_warnings=[],
        matching_enabled=matching_enabled,
        expires_at=expires_at or NOW + timedelta(days=30),
    )


def make_embedding(
    candidate_id: str = "cand-1",
    profile_version: int = 1,
    *,
    vector: list[float] | None = None,
    embedding_version: str = "emb-v1",
) -> EmbeddingRecord:
    values = vector or [0.6, 0.8]
    return EmbeddingRecord(
        entity_id=candidate_id,
        entity_version=profile_version,
        vector=values,
        model_id="deterministic-hash",
        model_revision="local-1",
        dimensions=len(values),
        preprocessing_version="pre-v1",
        embedding_version=embedding_version,
    )


def profile_ready(candidate_id: str = "cand-1", profile_version: int = 1) -> ProfileReadyEvent:
    return ProfileReadyEvent(
        event_id=f"evt-profile-{candidate_id}-{profile_version}",
        event_type="profile.ready",
        candidate_id=candidate_id,
        profile_version=profile_version,
        occurred_at=NOW,
    )


def job_change(
    job_id: str = "job-1",
    job_version: int = 1,
    event_type: str = "job.created",
    event_id: str | None = None,
) -> JobChangeEvent:
    return JobChangeEvent(
        event_id=event_id or f"evt-{event_type}-{job_id}-{job_version}",
        event_type=event_type,
        job_id=job_id,
        job_version=job_version,
        occurred_at=NOW,
        content_ref=f"{job_id}:{job_version}",
    )
