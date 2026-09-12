"""Builders for `app/modules/matching` tests. Owner: M2."""

from datetime import UTC, datetime, timedelta

from app.contracts.models import (
    CandidateProfile,
    EvidenceRef,
    Experience,
    Project,
    SkillEvidence,
)

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def evidence(document_id: str = "resume-1", excerpt: str = "Evidence.") -> EvidenceRef:
    return EvidenceRef(
        document_id=document_id,
        document_version=1,
        chunk_id="section",
        start=0,
        end=len(excerpt),
        excerpt=excerpt,
    )


def make_candidate(
    candidate_id: str = "cand-1",
    *,
    summary: str | None = "Backend engineer.",
    skills: list[SkillEvidence] | None = None,
    experience: list[Experience] | None = None,
    projects: list[Project] | None = None,
    profile_evidence: list[EvidenceRef] | None = None,
) -> CandidateProfile:
    return CandidateProfile(
        candidate_id=candidate_id,
        resume_id=f"resume-{candidate_id}",
        profile_version=1,
        language="en",
        summary=summary,
        skills=skills
        if skills is not None
        else [SkillEvidence(name="Python", evidence=[evidence()])],
        education=[],
        job_titles=[],
        organizations=[],
        experience=experience or [],
        estimated_experience_years=3.0,
        projects=projects or [],
        evidence=profile_evidence if profile_evidence is not None else [evidence()],
        extraction_warnings=[],
        matching_enabled=True,
        expires_at=NOW + timedelta(days=30),
    )
