"""Wiring for the C-08 incremental-matching tests. Owner: M3."""

import pytest

from app.core.clock import FixedClock
from app.db.app.matches import SqlMatchRepository, SqlRecommendationRepository
from app.db.app.profiles import SqlProfileRepository
from app.db.app.queue import SqlMatchQueue
from app.db.app.sessions import SqlSessionStore
from app.orchestration.job_events import MatchService, OutboxDispatcher
from app.orchestration.refresh import RecommendationPublisher
from app.orchestration.runs import SqlMatchRunRepository
from app.orchestration.worker import MatchWorker
from app.testing.memory import MemoryJobs
from tests.integration.fakes import CountingMatcher


@pytest.fixture
def jobs():
    """M2's in-memory JobRepository/JobEventOutbox double."""
    return MemoryJobs()


@pytest.fixture
def matcher():
    return CountingMatcher(scores={"job-1": 77.0, "job-2": 84.0, "job-3": 61.0})


@pytest.fixture
def wiring(app_session_factory, clock: FixedClock, jobs, matcher):
    profiles = SqlProfileRepository(app_session_factory, clock)
    matches = SqlMatchRepository(app_session_factory)
    recommendations = SqlRecommendationRepository(app_session_factory, clock)
    publisher = RecommendationPublisher(profiles, jobs, matches, recommendations)
    runs = SqlMatchRunRepository(app_session_factory, clock)
    queue = SqlMatchQueue(app_session_factory, clock, lease_seconds=300, max_attempts=3)
    service = MatchService(profiles, jobs, matches, matcher, publisher, runs, clock, batch_size=2)
    dispatcher = OutboxDispatcher(jobs, queue)
    worker = MatchWorker(queue, service, clock, dispatcher)
    return {
        "sessions": SqlSessionStore(app_session_factory, clock),
        "profiles": profiles,
        "matches": matches,
        "recommendations": recommendations,
        "runs": runs,
        "queue": queue,
        "service": service,
        "dispatcher": dispatcher,
        "worker": worker,
        "jobs": jobs,
        "matcher": matcher,
        "clock": clock,
    }
