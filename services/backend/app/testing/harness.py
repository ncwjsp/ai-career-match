"""Contract exercise, not a durable worker, ranker or production dispatcher."""

from datetime import datetime

from app.contracts.interfaces import JobRepository, Matcher, MatchRepository, ProfileRepository
from app.contracts.models import DomainEvent, JobChangeEvent, ProfileReadyEvent


class FixtureMatchHarness:
    def __init__(
        self,
        profiles: ProfileRepository,
        jobs: JobRepository,
        matches: MatchRepository,
        matcher: Matcher,
        now: datetime,
    ):
        self.profiles = profiles
        self.jobs = jobs
        self.matches = matches
        self.matcher = matcher
        self.now = now

    def handle(self, event: DomainEvent):
        if isinstance(event, ProfileReadyEvent):
            profile = self.profiles.get(event.candidate_id)
            if (
                profile is None
                or profile.profile_version != event.profile_version
                or not profile.matching_enabled
                or profile.expires_at <= self.now
            ):
                return []
            results = [
                self.matcher.score_pair(profile, job, "semantic-skills-v1")
                for job in self.jobs.list_active(self.now)
            ]
        elif isinstance(event, JobChangeEvent):
            current = self.jobs.get(event.job_id)
            if current is None or current.content_version != event.job_version:
                return []
            if event.event_type in ("job.expired", "job.removed"):
                self.matches.remove_job(event.job_id)
                return []
            if not current.active or (current.expires_at and current.expires_at <= self.now):
                return []
            results = []
            after_id = None
            while batch := self.profiles.list_active(self.now, limit=100, after_id=after_id):
                results.extend(self.matcher.match_job(current, batch, "semantic-skills-v1"))
                after_id = batch[-1].candidate_id
        else:
            raise NotImplementedError("Reconciliation belongs to C-08.")
        for result in results:
            self.matches.upsert(result)
        return results
