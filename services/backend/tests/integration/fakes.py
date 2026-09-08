"""Deterministic stand-ins for M1/M2 work. Owner: M3.

These are not implementations of A-03 or B-04: they return fixed, obviously
synthetic values so C-08's dispatch, batching, recovery and publication
behavior can be tested before real parsing and scoring exist.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contracts.models import (
    CandidateProfile,
    JobPosting,
    MatchResult,
    ScoreComponents,
    SkillComparison,
)
from tests.app.factories import evidence


class CountingMatcher:
    """Scores a pair from a fixed table and records every call it was asked to make."""

    def __init__(self, scores: dict[str, float] | None = None, default: float = 50.0):
        self._scores = scores or {}
        self._default = default
        self.pair_calls: list[tuple[str, str]] = []

    def score_pair(
        self, profile: CandidateProfile, job: JobPosting, scoring_version: str
    ) -> MatchResult:
        self.pair_calls.append((profile.candidate_id, job.job_id))
        score = self._scores.get(job.job_id, self._default)
        return MatchResult(
            candidate_id=profile.candidate_id,
            profile_version=profile.profile_version,
            job_id=job.job_id,
            job_version=job.content_version,
            score=score,
            score_components=ScoreComponents(
                semantic_fit=score / 100,
                skill_coverage=None,
                semantic_weight=1.0,
                skills_weight=0.0,
                score_basis="semantic_only",
                model_revision="local-1",
                preprocessing_version="pre-v1",
            ),
            scoring_version=scoring_version,
            skill_comparison=[
                SkillComparison(
                    skill="Python",
                    required=True,
                    state="present",
                    job_evidence=[evidence(document_id=job.job_id, excerpt="Required: Python.")],
                    resume_evidence=[evidence()],
                )
            ],
            strengths=["Strong Python experience"],
            gaps=[],
            short_reason=None,
            evidence=[evidence()],
            matched_at=job.last_seen_at,
            data_origin="computed",
        )

    def match_job(
        self, job: JobPosting, active_profiles: Sequence[CandidateProfile], scoring_version: str
    ) -> Sequence[MatchResult]:
        return [self.score_pair(profile, job, scoring_version) for profile in active_profiles]

    def recommend(self, profile: CandidateProfile, corpus_snapshot: str, limit: int):
        raise NotImplementedError("Ranking belongs to M2; C-08 publishes stored scores.")


class ExplodingResumeProcessor:
    """Fails loudly if anything tries to reparse a resume during job matching."""

    def process(self, file):
        raise AssertionError("A job-change refresh must never call the resume parser.")


class FlakyQueue:
    """Wraps a queue and refuses the nth enqueue, to test the outbox handoff."""

    def __init__(self, queue, fail_on: int):
        self._queue = queue
        self._fail_on = fail_on
        self._seen = 0

    def enqueue(self, event) -> bool:
        self._seen += 1
        if self._seen == self._fail_on:
            raise RuntimeError("career_app is unreachable")
        return self._queue.enqueue(event)

    def claim(self):
        return self._queue.claim()

    def acknowledge(self, event_id: str) -> None:
        self._queue.acknowledge(event_id)

    def retry(self, event_id: str, error: str | None = None) -> None:
        self._queue.retry(event_id, error)
