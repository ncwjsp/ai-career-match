"""Canonical v1 DTOs. M3 maintains these after Plai's bootstrap handoff."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    HttpUrl,
    StringConstraints,
    model_validator,
)

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
Text = Annotated[str, StringConstraints(min_length=1)]
Version = Annotated[int, Field(ge=1)]
Fraction = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Percentage = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EvidenceRef(Contract):
    document_id: Identifier
    document_version: Version
    chunk_id: Identifier
    page: Annotated[int, Field(ge=1)] | None = None
    section: str | None = None
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    excerpt: Text

    @model_validator(mode="after")
    def valid_span(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Evidence end must follow start.")
        return self


class SkillEvidence(Contract):
    name: Text
    evidence: Annotated[list[EvidenceRef], Field(min_length=1)]


class Education(Contract):
    institution: str | None
    qualification: str | None
    evidence: Annotated[list[EvidenceRef], Field(min_length=1)]


class Experience(Contract):
    job_title: str | None
    organization: str | None
    start_date: str | None = None
    end_date: str | None = None
    evidence: Annotated[list[EvidenceRef], Field(min_length=1)]


class Project(Contract):
    name: Text
    description: Text
    evidence: Annotated[list[EvidenceRef], Field(min_length=1)]


class CandidateProfile(Contract):
    candidate_id: Identifier
    resume_id: Identifier
    profile_version: Version
    language: str | None
    summary: str | None
    skills: list[SkillEvidence]
    education: list[Education]
    job_titles: list[str]
    organizations: list[str]
    experience: list[Experience]
    estimated_experience_years: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    projects: list[Project]
    evidence: list[EvidenceRef]
    extraction_warnings: list[str]
    matching_enabled: bool
    expires_at: AwareDatetime


class JobRequirement(Contract):
    skill: Text
    required: bool
    evidence: Annotated[list[EvidenceRef], Field(min_length=1)]


class JobPosting(Contract):
    job_id: Identifier
    source_id: Identifier
    source_url: HttpUrl
    content_version: Version
    title: Text
    company: Text
    description: Text
    summary: str | None
    requirements: list[JobRequirement]
    other_requirements: list[str]
    evidence: list[EvidenceRef]
    language: str | None
    fetched_at: AwareDatetime
    last_seen_at: AwareDatetime
    posted_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    active: bool
    data_origin: Literal["fixture", "permitted_source"]


class EmbeddingRecord(Contract):
    entity_id: Identifier
    entity_version: Version
    vector: Annotated[list[FiniteFloat], Field(min_length=1)]
    model_id: Text
    model_revision: Text
    dimensions: Annotated[int, Field(gt=0)]
    preprocessing_version: Text
    embedding_version: Text

    @model_validator(mode="after")
    def valid_vector(self) -> Self:
        if len(self.vector) != self.dimensions or not any(self.vector):
            raise ValueError("Vector must be nonzero and match declared dimensions.")
        return self


class SkillComparison(Contract):
    skill: Text
    required: bool
    state: Literal["present", "partial", "missing"]
    job_evidence: Annotated[list[EvidenceRef], Field(min_length=1)]
    resume_evidence: list[EvidenceRef]
    uncertainty_note: str | None = None

    @model_validator(mode="after")
    def evidence_matches_state(self) -> Self:
        if self.state == "missing" and self.resume_evidence:
            raise ValueError("A missing skill cannot carry supporting resume evidence.")
        if self.state != "missing" and not self.resume_evidence:
            raise ValueError("Present/partial skills require resume evidence.")
        return self


class ScoreComponents(Contract):
    semantic_fit: Fraction
    skill_coverage: Fraction | None
    semantic_weight: Fraction
    skills_weight: Fraction
    score_basis: Literal["semantic_skills", "semantic_only"]
    model_revision: Text
    preprocessing_version: Text

    @model_validator(mode="after")
    def valid_weights(self) -> Self:
        if abs(self.semantic_weight + self.skills_weight - 1) > 1e-9:
            raise ValueError("Score weights must sum to one.")
        if self.score_basis == "semantic_only":
            if self.skill_coverage is not None or self.skills_weight != 0:
                raise ValueError("Semantic-only score has no skill coverage term.")
        elif self.skill_coverage is None:
            raise ValueError("Semantic/skills score requires coverage.")
        return self


class MatchResult(Contract):
    candidate_id: Identifier
    profile_version: Version
    job_id: Identifier
    job_version: Version
    score: Percentage
    score_components: ScoreComponents
    scoring_version: Text
    skill_comparison: list[SkillComparison]
    strengths: list[str]
    gaps: list[str]
    short_reason: str | None
    evidence: list[EvidenceRef]
    matched_at: AwareDatetime
    data_origin: Literal["fixture", "computed"]


class Recommendation(MatchResult):
    match_run_id: Identifier
    revision: Version
    rank: Annotated[int, Field(ge=1)]
    job_summary: str | None
    source_url: HttpUrl
    last_seen_at: AwareDatetime
    index_version: Text
    analysis_id: Identifier | None = None


class RecommendationSet(Contract):
    candidate_id: Identifier
    profile_version: Version
    revision: Version
    updated_at: AwareDatetime
    refresh_state: Literal["idle", "pending", "failed"]
    results: list[Recommendation]
    next_cursor: str | None = None

    @model_validator(mode="after")
    def coherent_revision(self) -> Self:
        ranks = []
        for result in self.results:
            if (result.candidate_id, result.profile_version, result.revision) != (
                self.candidate_id,
                self.profile_version,
                self.revision,
            ):
                raise ValueError("Results must share the candidate/profile/revision.")
            ranks.append(result.rank)
        if ranks != sorted(set(ranks)):
            raise ValueError("Ranks must be ordered and unique.")
        return self


class MatchExplanation(Contract):
    candidate_id: Identifier
    revision: Version
    profile_version: Version
    job_id: Identifier
    job_version: Version
    scoring_version: Text
    state: Literal["pending", "ready", "unavailable"]
    text: str | None
    strengths: list[str]
    gaps: list[str]
    evidence: list[EvidenceRef]
    model_version: str | None
    prompt_version: str | None
    generated_at: AwareDatetime | None


class ErrorDetail(Contract):
    code: Text
    message: Text
    retryable: bool
    request_id: Text


class ErrorResponse(Contract):
    error: ErrorDetail


class UploadAccepted(Contract):
    candidate_id: Identifier
    resume_id: Identifier
    analysis_id: Identifier
    status_url: Text


class AnalysisRun(Contract):
    analysis_id: Identifier
    candidate_id: Identifier
    resume_id: Identifier
    state: Literal["queued", "extracting", "profiling", "matching", "ready", "failed"]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    corpus_snapshot: str | None
    warnings: list[str]
    error: ErrorDetail | None
    result_count: Annotated[int, Field(ge=0)]


class ProfileReadyEvent(Contract):
    schema_version: Literal[1] = 1
    event_id: Identifier
    event_type: Literal["profile.ready"]
    candidate_id: Identifier
    profile_version: Version
    occurred_at: AwareDatetime


class JobChangeEvent(Contract):
    schema_version: Literal[1] = 1
    event_id: Identifier
    event_type: Literal["job.created", "job.updated", "job.expired", "job.removed"]
    job_id: Identifier
    job_version: Version
    occurred_at: AwareDatetime
    content_ref: Text


class ReconciliationEvent(Contract):
    schema_version: Literal[1] = 1
    event_id: Identifier
    event_type: Literal["reconciliation.requested"]
    occurred_at: AwareDatetime
    candidate_after_id: Identifier | None = None


DomainEvent = Annotated[
    ProfileReadyEvent | JobChangeEvent | ReconciliationEvent, Field(discriminator="event_type")
]


class MatchRun(Contract):
    run_id: Identifier
    event: DomainEvent
    state: Literal["queued", "running", "ready", "failed"]
    checkpoint: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    error: ErrorDetail | None
    published_revisions: dict[str, int]


class FileRef(Contract):
    object_key: Text
    media_type: Text


class ProcessedText(Contract):
    text: Text
    language: str | None
    evidence: list[EvidenceRef]
    preprocessing_version: Text


class IngestionReport(Contract):
    run_id: Identifier
    new_jobs: Annotated[int, Field(ge=0)]
    changed_jobs: Annotated[int, Field(ge=0)]
    unchanged_jobs: Annotated[int, Field(ge=0)]
    event_ids: list[Identifier]
    warnings: list[str]


class FixtureBundle(Contract):
    mode: Literal["fixture"] = "fixture"
    description: Text
    profiles: list[CandidateProfile]
    jobs: list[JobPosting]
    embeddings: list[EmbeddingRecord]
    events: list[DomainEvent]
    matches: list[MatchResult]
    recommendations: RecommendationSet
    explanation: MatchExplanation
    analysis: AnalysisRun
    match_runs: list[MatchRun]
    errors: list[ErrorResponse]
