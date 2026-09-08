"""Job-change dispatch and incremental matching. Owner: M3 (C-08).

Two pieces, in the order a job travels:

1. `OutboxDispatcher` moves committed rows from M2's `career_jobs` outbox into
   M3's `career_app` queue. The two databases have no shared transaction, so the
   handoff is at-least-once by construction: the event is inserted durably in
   `career_app` **first**, and only then acknowledged in `career_jobs`. A crash
   between those two steps redelivers the event, and the queue's `event_id`
   primary key turns that into a no-op. Losing an event is not possible; seeing
   one twice is, and is handled.

2. `MatchService` consumes one event. `profile.ready` scores the new profile
   against the active corpus. `job.created` / `job.updated` score one job
   against every retained active candidate, in bounded batches with a
   checkpoint after each batch. `job.expired` / `job.removed` drop that job's
   scores and republish the affected candidates. `reconciliation.requested`
   walks retained candidates and republishes anyone whose stored scores no
   longer match their published revision.

Nothing here touches the browser, the upload handler or the resume parser: a
new job refreshes a week-old candidate while their tab is closed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.contracts.interfaces import (
    JobEventOutbox,
    JobRepository,
    Matcher,
    MatchQueue,
    MatchRepository,
)
from app.contracts.models import (
    DomainEvent,
    JobChangeEvent,
    MatchResult,
    ProfileReadyEvent,
    ReconciliationEvent,
)
from app.core.clock import Clock
from app.db.app.profiles import SqlProfileRepository
from app.orchestration.refresh import RecommendationPublisher
from app.orchestration.runs import SqlMatchRunRepository

CLEANUP_EVENTS = ("job.expired", "job.removed")


class OutboxDispatcher:
    """Copies committed job-change events into the durable application queue."""

    def __init__(self, outbox: JobEventOutbox, queue: MatchQueue, batch_size: int = 100):
        self._outbox = outbox
        self._queue = queue
        self._batch_size = batch_size

    def dispatch_once(self) -> int:
        """Move one batch. Returns how many events were newly accepted."""
        accepted = 0
        for event in self._outbox.pending(limit=self._batch_size):
            # Durable insert first; acknowledge second. Never the other way round.
            if self._queue.enqueue(event):
                accepted += 1
            self._outbox.acknowledge(event.event_id)
        return accepted


class MatchService:
    """Handles one durable event. `handle` is safe to call twice for one event."""

    def __init__(
        self,
        profiles: SqlProfileRepository,
        jobs: JobRepository,
        matches: MatchRepository,
        matcher: Matcher,
        publisher: RecommendationPublisher,
        runs: SqlMatchRunRepository,
        clock: Clock,
        *,
        batch_size: int = 100,
        scoring_version: str = "semantic-skills-v1",
    ):
        self._profiles = profiles
        self._jobs = jobs
        self._matches = matches
        self._matcher = matcher
        self._publisher = publisher
        self._runs = runs
        self._clock = clock
        self._batch_size = batch_size
        self._scoring_version = scoring_version

    def handle(self, event: DomainEvent) -> Sequence[MatchResult]:
        run = self._runs.start(event)
        now = self._clock.now()
        try:
            if isinstance(event, ProfileReadyEvent):
                results = self._handle_profile_ready(event, run.run_id, now)
            elif isinstance(event, JobChangeEvent):
                results = self._handle_job_change(event, run.run_id, now)
            elif isinstance(event, ReconciliationEvent):
                results = self._handle_reconciliation(event, run.run_id, now)
            else:  # pragma: no cover - DomainEvent is a closed union
                raise NotImplementedError(f"Unhandled event type {event.event_type!r}.")
        except Exception:
            # The queue owns retry and backoff; the run row records the state.
            self._runs.fail(run.run_id, _failure())
            raise
        self._runs.finish(run.run_id)
        return results

    def _handle_profile_ready(
        self, event: ProfileReadyEvent, run_id: str, now: datetime
    ) -> Sequence[MatchResult]:
        profile = self._profiles.get(event.candidate_id)
        if (
            profile is None
            or profile.profile_version != event.profile_version
            or not self._profiles.is_active(event.candidate_id, now)
        ):
            # A replaced, expired or deleted profile: the event is obsolete, not failed.
            return []
        results = [
            self._matcher.score_pair(profile, job, self._scoring_version)
            for job in self._jobs.list_active(now)
        ]
        for result in results:
            self._matches.upsert(result)
        self._publish(event.candidate_id, now, run_id)
        return results

    def _handle_job_change(
        self, event: JobChangeEvent, run_id: str, now: datetime
    ) -> Sequence[MatchResult]:
        if event.event_type in CLEANUP_EVENTS:
            return self._retire_job(event.job_id, run_id, now)

        job = self._jobs.get(event.job_id)
        if job is None or job.content_version != event.job_version:
            # A newer version already arrived; scoring this one would publish
            # a ranking that cites content nobody can read any more.
            return []
        if not job.active or (job.expires_at is not None and job.expires_at <= now):
            return self._retire_job(event.job_id, run_id, now)

        results: list[MatchResult] = []
        touched: list[str] = []
        after_id = self._runs.get(run_id).checkpoint
        while batch := self._profiles.list_active(now, limit=self._batch_size, after_id=after_id):
            scored = self._matcher.match_job(job, batch, self._scoring_version)
            for result in scored:
                self._matches.upsert(result)
            results.extend(scored)
            touched.extend(profile.candidate_id for profile in batch)
            after_id = batch[-1].candidate_id
            # Checkpoint after the batch is stored: a restart resumes here.
            self._runs.checkpoint(run_id, after_id)
        for candidate_id in touched:
            self._publish(candidate_id, now, run_id)
        return results

    def _retire_job(self, job_id: str, run_id: str, now: datetime) -> Sequence[MatchResult]:
        affected = self._candidates_with_job(job_id, now)
        self._matches.remove_job(job_id)
        for candidate_id in affected:
            self._publish(candidate_id, now, run_id)
        return []

    def _candidates_with_job(self, job_id: str, now: datetime) -> list[str]:
        affected: list[str] = []
        after_id = None
        while batch := self._profiles.list_active(now, limit=self._batch_size, after_id=after_id):
            for profile in batch:
                stored = self._matches.list_for_candidate(
                    profile.candidate_id, profile.profile_version
                )
                if any(result.job_id == job_id for result in stored):
                    affected.append(profile.candidate_id)
            after_id = batch[-1].candidate_id
        return affected

    def _handle_reconciliation(
        self, event: ReconciliationEvent, run_id: str, now: datetime
    ) -> Sequence[MatchResult]:
        after_id = event.candidate_after_id or self._runs.get(run_id).checkpoint
        while batch := self._profiles.list_active(now, limit=self._batch_size, after_id=after_id):
            for profile in batch:
                # publish_for is a no-op when the published revision already
                # matches the stored scores, so reconciliation is cheap to rerun.
                self._publish(profile.candidate_id, now, run_id)
            after_id = batch[-1].candidate_id
            self._runs.checkpoint(run_id, after_id)
        return []

    def _publish(self, candidate_id: str, now: datetime, run_id: str) -> None:
        published = self._publisher.publish_for(candidate_id, now, match_run_id=run_id)
        if published is not None:
            self._runs.record_revision(run_id, candidate_id, published.revision)


def _failure():
    from app.contracts.models import ErrorDetail
    from app.core.ids import new_id

    return ErrorDetail(
        code="MATCH_RUN_FAILED",
        # The exception text can quote job or resume content; keep it in logs only.
        message="The match run failed and will be retried.",
        retryable=True,
        request_id=new_id("req"),
    )
