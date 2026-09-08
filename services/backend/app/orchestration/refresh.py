"""Recommendation revision publication. Owner: M3 (C-08).

Both matching triggers end here: after scores exist, one coherent ranked
revision is published for the affected candidate. The browser is not involved,
so a candidate who uploaded a resume last week and closed the tab still gets a
refreshed revision when a new job arrives.

Reads exclude inactive and expired postings even before a cleanup event has
been processed, so a stale posting cannot be published as a recommendation just
because its `job.expired` event has not been consumed yet.
"""

from __future__ import annotations

from datetime import datetime

from app.contracts.interfaces import JobRepository, MatchRepository
from app.contracts.models import JobPosting, MatchResult, Recommendation, RecommendationSet
from app.db.app.matches import SqlRecommendationRepository
from app.db.app.profiles import SqlProfileRepository


class RecommendationPublisher:
    def __init__(
        self,
        profiles: SqlProfileRepository,
        jobs: JobRepository,
        matches: MatchRepository,
        recommendations: SqlRecommendationRepository,
        index_version: str = "exact-cosine-v1",
    ):
        self._profiles = profiles
        self._jobs = jobs
        self._matches = matches
        self._recommendations = recommendations
        self._index_version = index_version

    def publish_for(
        self,
        candidate_id: str,
        now: datetime,
        *,
        match_run_id: str,
        analysis_id: str | None = None,
        refresh_state: str = "idle",
    ) -> RecommendationSet | None:
        """Publish the next revision for one candidate, or None if nothing changed.

        Returns None when the candidate is no longer matchable: retention is
        re-checked here, immediately before publication, so a profile that
        expired or was disabled during a long run never gains a new revision.
        """
        profile = self._profiles.get(candidate_id)
        if profile is None or not self._profiles.is_active(candidate_id, now):
            return None

        ranked = self._rank(candidate_id, profile.profile_version, now)
        latest = self._recommendations.latest(candidate_id)
        if latest is not None and _same_ranking(latest, ranked):
            return None  # Nothing changed for this candidate; do not churn revisions.

        revision = self._recommendations.next_revision(candidate_id)
        results = [
            self._to_recommendation(result, job, revision, rank, match_run_id, analysis_id)
            for rank, (result, job) in enumerate(ranked, start=1)
        ]
        result_set = RecommendationSet(
            candidate_id=candidate_id,
            profile_version=profile.profile_version,
            revision=revision,
            updated_at=now,
            refresh_state=refresh_state,
            results=results,
            next_cursor=None,
        )
        self._recommendations.publish(result_set)
        return result_set

    def _rank(
        self, candidate_id: str, profile_version: int, now: datetime
    ) -> list[tuple[MatchResult, JobPosting]]:
        ranked: list[tuple[MatchResult, JobPosting]] = []
        current: dict[str, JobPosting | None] = {}
        for result in self._matches.list_for_candidate(candidate_id, profile_version):
            if result.job_id not in current:
                current[result.job_id] = self._jobs.get(result.job_id)
            job = current[result.job_id]
            if job is None or not job.active:
                continue
            if job.content_version != result.job_version:
                # A score for a superseded version of a job the reader can no
                # longer see. The new version is scored before it is published,
                # so dropping it here never hides a current posting twice.
                continue
            if job.expires_at is not None and job.expires_at <= now:
                continue
            ranked.append((result, job))
        # Sort on the unrounded score with a stable job-id tie-break, as the plan's
        # scoring section requires, then rank.
        ranked.sort(key=lambda pair: (-pair[0].score, pair[0].job_id))
        return ranked

    def _to_recommendation(
        self,
        result: MatchResult,
        job: JobPosting,
        revision: int,
        rank: int,
        match_run_id: str,
        analysis_id: str | None,
    ) -> Recommendation:
        return Recommendation(
            **result.model_dump(),
            match_run_id=match_run_id,
            revision=revision,
            rank=rank,
            job_summary=job.summary,
            source_url=job.source_url,
            last_seen_at=job.last_seen_at,
            index_version=self._index_version,
            analysis_id=analysis_id,
        )


def _same_ranking(
    published: RecommendationSet, ranked: list[tuple[MatchResult, JobPosting]]
) -> bool:
    """Compare what a reader would see: the same jobs, versions and scores in order."""
    current = [(entry.job_id, entry.job_version, entry.score) for entry in published.results]
    candidate = [(result.job_id, result.job_version, result.score) for result, _ in ranked]
    return current == candidate
