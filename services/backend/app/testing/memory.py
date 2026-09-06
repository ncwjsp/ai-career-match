"""In-memory test doubles. Data is lost on exit; these do not complete C-01/B-09."""

from collections import deque
from datetime import datetime

from app.contracts.models import (
    CandidateProfile,
    DomainEvent,
    JobChangeEvent,
    JobPosting,
    MatchResult,
)


class MemoryProfiles:
    def __init__(self, profiles=()):
        self._profiles = {p.candidate_id: p.model_copy(deep=True) for p in profiles}

    def get(self, candidate_id: str) -> CandidateProfile | None:
        result = self._profiles.get(candidate_id)
        return result.model_copy(deep=True) if result else None

    def save(self, profile: CandidateProfile) -> None:
        self._profiles[profile.candidate_id] = profile.model_copy(deep=True)

    def list_active(self, at: datetime, limit: int = 100, after_id: str | None = None):
        return [
            self.get(key)
            for key in sorted(self._profiles)
            if self._profiles[key].matching_enabled
            and self._profiles[key].expires_at > at
            and (after_id is None or key > after_id)
        ][:limit]


class MemoryJobs:
    def __init__(self, jobs=()):
        self._jobs = {(j.job_id, j.content_version): j.model_copy(deep=True) for j in jobs}
        self._events: dict[str, JobChangeEvent] = {}

    def get(self, job_id: str, version: int | None = None) -> JobPosting | None:
        versions = [v for key, v in self._jobs if key == job_id]
        if not versions:
            return None
        job = self._jobs.get((job_id, version if version is not None else max(versions)))
        return job.model_copy(deep=True) if job else None

    def list_active(self, at: datetime):
        jobs = [self.get(key) for key in sorted({key for key, _ in self._jobs})]
        return [j for j in jobs if j and j.active and (j.expires_at is None or j.expires_at > at)]

    def save_with_event(self, job: JobPosting, event: JobChangeEvent) -> None:
        if (job.job_id, job.content_version) != (event.job_id, event.job_version):
            raise ValueError("Job and event versions must match.")
        if event.event_id in self._events:
            if self._events[event.event_id] != event:
                raise ValueError("An event_id cannot identify different events.")
            return
        self._jobs[(job.job_id, job.content_version)] = job.model_copy(deep=True)
        self._events[event.event_id] = event.model_copy(deep=True)

    def pending(self, limit: int = 100):
        return [e.model_copy(deep=True) for e in list(self._events.values())[:limit]]

    def acknowledge(self, event_id: str):
        self._events.pop(event_id, None)


class MemoryMatches:
    def __init__(self):
        self._matches: dict[tuple, MatchResult] = {}

    def upsert(self, result: MatchResult):
        key = (
            result.candidate_id,
            result.profile_version,
            result.job_id,
            result.job_version,
            result.scoring_version,
        )
        self._matches[key] = result.model_copy(deep=True)

    def list_for_candidate(self, candidate_id: str, profile_version: int):
        return [
            r.model_copy(deep=True)
            for r in self._matches.values()
            if r.candidate_id == candidate_id and r.profile_version == profile_version
        ]

    def remove_job(self, job_id: str):
        self._matches = {key: r for key, r in self._matches.items() if r.job_id != job_id}


class MemoryQueue:
    def __init__(self):
        self._known: dict[str, DomainEvent] = {}
        self._pending: deque[str] = deque()
        self._inflight: set[str] = set()

    def enqueue(self, event: DomainEvent) -> bool:
        if event.event_id in self._known:
            if event != self._known[event.event_id]:
                raise ValueError("An event_id cannot identify different events.")
            return False
        self._known[event.event_id] = event.model_copy(deep=True)
        self._pending.append(event.event_id)
        return True

    def claim(self):
        if not self._pending:
            return None
        key = self._pending.popleft()
        self._inflight.add(key)
        return self._known[key].model_copy(deep=True)

    def acknowledge(self, event_id: str):
        self._inflight.discard(event_id)

    def retry(self, event_id: str):
        if event_id in self._inflight:
            self._inflight.remove(event_id)
            self._pending.append(event_id)
