"""Builders for `career_app` test fixtures. Owner: M3 (C-01)."""

from datetime import UTC, datetime, timedelta

from app.contracts.models import (
    CandidateProfile,
    EmbeddingRecord,
    EvidenceRef,
    JobChangeEvent,
    MatchResult,
    ProfileReadyEvent,
    Recommendation,
    RecommendationSet,
    ScoreComponents,
    SkillComparison,
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


def score_components(semantic: float = 0.80, coverage: float | None = 0.70) -> ScoreComponents:
    if coverage is None:
        return ScoreComponents(
            semantic_fit=semantic,
            skill_coverage=None,
            semantic_weight=1.0,
            skills_weight=0.0,
            score_basis="semantic_only",
            model_revision="local-1",
            preprocessing_version="pre-v1",
        )
    return ScoreComponents(
        semantic_fit=semantic,
        skill_coverage=coverage,
        semantic_weight=0.70,
        skills_weight=0.30,
        score_basis="semantic_skills",
        model_revision="local-1",
        preprocessing_version="pre-v1",
    )


def skill_comparison(state: str = "present") -> SkillComparison:
    return SkillComparison(
        skill="Python",
        required=True,
        state=state,
        job_evidence=[evidence(document_id="job-1", excerpt="Required: Python.")],
        resume_evidence=[] if state == "missing" else [evidence()],
    )


def make_match(
    candidate_id: str = "cand-1",
    job_id: str = "job-1",
    *,
    profile_version: int = 1,
    job_version: int = 1,
    score: float = 77.0,
    scoring_version: str = "semantic-skills-v1",
) -> MatchResult:
    """The plan's worked example: S=0.80, K=0.70 gives 77.0%."""
    return MatchResult(
        candidate_id=candidate_id,
        profile_version=profile_version,
        job_id=job_id,
        job_version=job_version,
        score=score,
        score_components=score_components(),
        scoring_version=scoring_version,
        skill_comparison=[skill_comparison()],
        strengths=["Strong Python experience"],
        gaps=["Docker"],
        short_reason=None,
        evidence=[evidence()],
        matched_at=NOW,
        data_origin="fixture",
    )


def make_recommendation(
    candidate_id: str = "cand-1",
    job_id: str = "job-1",
    *,
    rank: int = 1,
    revision: int = 1,
    score: float = 77.0,
    job_version: int = 1,
    match_run_id: str = "run-1",
) -> Recommendation:
    base = make_match(candidate_id, job_id, score=score, job_version=job_version)
    return Recommendation(
        **base.model_dump(),
        match_run_id=match_run_id,
        revision=revision,
        rank=rank,
        job_summary="NLP engineer at Example Labs.",
        source_url="https://jobs.example.test/job-1",
        last_seen_at=NOW,
        index_version="idx-v1",
    )


def make_recommendation_set(
    candidate_id: str = "cand-1",
    *,
    revision: int = 1,
    jobs: tuple[str, ...] = ("job-1", "job-2"),
    refresh_state: str = "idle",
) -> RecommendationSet:
    results = [
        make_recommendation(
            candidate_id, job_id, rank=index + 1, revision=revision, score=90.0 - index
        )
        for index, job_id in enumerate(jobs)
    ]
    return RecommendationSet(
        candidate_id=candidate_id,
        profile_version=1,
        revision=revision,
        updated_at=NOW,
        refresh_state=refresh_state,
        results=results,
        next_cursor=None,
    )
