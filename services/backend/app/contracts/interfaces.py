"""Ports, not implementations. M3 coordinates changes with each domain owner."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.contracts.models import (
    AnalysisRun,
    CandidateProfile,
    DomainEvent,
    EmbeddingRecord,
    FileRef,
    IngestionReport,
    JobChangeEvent,
    JobPosting,
    MatchExplanation,
    MatchResult,
    ProcessedText,
    Recommendation,
    RecommendationSet,
)


class ProfileRepository(Protocol):
    def get(self, candidate_id: str) -> CandidateProfile | None: ...
    def save(self, profile: CandidateProfile) -> None: ...
    def list_active(
        self, at: datetime, limit: int = 100, after_id: str | None = None
    ) -> Sequence[CandidateProfile]: ...


class JobRepository(Protocol):
    def get(self, job_id: str, version: int | None = None) -> JobPosting | None: ...
    def list_active(self, at: datetime) -> Sequence[JobPosting]: ...
    def save_with_event(self, job: JobPosting, event: JobChangeEvent) -> None:
        """M2 must commit the job and outbox event in one career_jobs transaction."""
        ...


class JobEventOutbox(Protocol):
    def pending(self, limit: int = 100) -> Sequence[JobChangeEvent]: ...
    def acknowledge(self, event_id: str) -> None: ...


class MatchRepository(Protocol):
    def upsert(self, result: MatchResult) -> None: ...
    def list_for_candidate(
        self, candidate_id: str, profile_version: int
    ) -> Sequence[MatchResult]: ...
    def remove_job(self, job_id: str) -> None: ...


class RecommendationRepository(Protocol):
    def latest(self, candidate_id: str) -> RecommendationSet | None: ...
    def publish(self, result_set: RecommendationSet) -> None:
        """Publish a coherent, immutable revision atomically."""
        ...


class MatchQueue(Protocol):
    def enqueue(self, event: DomainEvent) -> bool:
        """Return False for an already accepted event_id."""
        ...

    def claim(self) -> DomainEvent | None: ...
    def acknowledge(self, event_id: str) -> None: ...
    def retry(self, event_id: str) -> None: ...


class AnalysisQueue(Protocol):
    def enqueue(self, run: AnalysisRun, file: FileRef) -> None: ...


class ObjectStore(Protocol):
    def put(self, content: bytes, media_type: str) -> FileRef: ...
    def read(self, file: FileRef) -> bytes: ...
    def delete(self, file: FileRef) -> None: ...


class ResumeProcessor(Protocol):
    def process(self, file: FileRef) -> CandidateProfile: ...


class TextProcessor(Protocol):
    def process(self, text: str, language: str | None) -> ProcessedText: ...


class Embedder(Protocol):
    def encode(self, texts: Sequence[ProcessedText], version: str) -> Sequence[EmbeddingRecord]: ...


class Matcher(Protocol):
    def score_pair(
        self, profile: CandidateProfile, job: JobPosting, scoring_version: str
    ) -> MatchResult: ...
    def recommend(
        self, profile: CandidateProfile, corpus_snapshot: str, limit: int
    ) -> Sequence[Recommendation]: ...
    def match_job(
        self, job: JobPosting, active_profiles: Sequence[CandidateProfile], scoring_version: str
    ) -> Sequence[MatchResult]: ...


class MatchWorker(Protocol):
    def handle(self, event: DomainEvent) -> Sequence[MatchResult]: ...


class JobIngestor(Protocol):
    def run(self, source_id: str) -> IngestionReport: ...


class Explainer(Protocol):
    def explain(
        self, profile: CandidateProfile, job: JobPosting, recommendation: Recommendation
    ) -> MatchExplanation: ...
