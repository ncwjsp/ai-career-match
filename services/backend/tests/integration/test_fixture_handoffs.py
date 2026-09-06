from datetime import UTC, datetime, timedelta

import pytest

from app.testing.adapters import FixtureMatcher
from app.testing.fixtures import load_fixtures
from app.testing.harness import FixtureMatchHarness
from app.testing.memory import MemoryJobs, MemoryMatches, MemoryProfiles, MemoryQueue

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def test_new_job_matches_existing_profile_without_any_upload_processor():
    fixtures = load_fixtures()
    profiles = MemoryProfiles(fixtures.profiles)
    jobs = MemoryJobs(fixtures.jobs[:1])
    matches = MemoryMatches()
    matcher = FixtureMatcher(fixtures)
    harness = FixtureMatchHarness(profiles, jobs, matches, matcher, NOW)

    first = harness.handle(fixtures.events[0])
    assert [r.job_id for r in first] == ["job-demo-1"]
    jobs.save_with_event(fixtures.jobs[1], fixtures.events[1])
    second = harness.handle(jobs.pending()[0])
    assert [r.job_id for r in second] == ["job-demo-2"]
    assert second[0] == matcher.score_pair(
        fixtures.profiles[0], fixtures.jobs[1], "semantic-skills-v1"
    )
    harness.handle(fixtures.events[1])
    assert len(matches.list_for_candidate("candidate-demo", 1)) == 2
    assert profiles.get("candidate-demo") == fixtures.profiles[0]


@pytest.mark.parametrize(
    "update",
    [
        {"matching_enabled": False},
        {"expires_at": NOW - timedelta(seconds=1)},
    ],
)
def test_inactive_candidates_are_excluded_from_both_triggers(update):
    fixtures = load_fixtures()
    profile = fixtures.profiles[0].model_copy(update=update)
    harness = FixtureMatchHarness(
        MemoryProfiles([profile]),
        MemoryJobs(fixtures.jobs),
        MemoryMatches(),
        FixtureMatcher(fixtures),
        NOW,
    )
    assert harness.handle(fixtures.events[0]) == []
    assert harness.handle(fixtures.events[1]) == []


def test_queue_replay_retry_and_event_identity():
    event = load_fixtures().events[1]
    queue = MemoryQueue()
    assert queue.enqueue(event)
    assert not queue.enqueue(event)
    assert queue.claim() == event
    assert queue.claim() is None
    queue.retry(event.event_id)
    assert queue.claim() == event
    queue.acknowledge(event.event_id)
    assert queue.claim() is None
    with pytest.raises(ValueError):
        queue.enqueue(event.model_copy(update={"job_version": 2}))


def test_job_event_and_record_must_be_same_version():
    fixtures = load_fixtures()
    jobs = MemoryJobs()
    bad_event = fixtures.events[1].model_copy(update={"job_version": 2})
    with pytest.raises(ValueError):
        jobs.save_with_event(fixtures.jobs[1], bad_event)
    assert jobs.get("job-demo-2") is None
    assert jobs.pending() == []


def test_unknown_fixture_pair_does_not_fabricate_a_score():
    fixtures = load_fixtures()
    with pytest.raises(NotImplementedError):
        FixtureMatcher(fixtures).score_pair(
            fixtures.profiles[0].model_copy(update={"profile_version": 2}),
            fixtures.jobs[0],
            "semantic-skills-v1",
        )


def test_stale_job_event_cannot_overwrite_current_matches():
    fixtures = load_fixtures()
    jobs = MemoryJobs(fixtures.jobs)
    newer_job = fixtures.jobs[1].model_copy(update={"content_version": 2})
    newer_event = fixtures.events[1].model_copy(
        update={"event_id": "event-job-v2", "job_version": 2, "event_type": "job.updated"}
    )
    jobs.save_with_event(newer_job, newer_event)
    harness = FixtureMatchHarness(
        MemoryProfiles(fixtures.profiles), jobs, MemoryMatches(), FixtureMatcher(fixtures), NOW
    )
    # The fixture matcher has no v2 score: an obsolete v1 event must be skipped before scoring.
    assert harness.handle(fixtures.events[1]) == []


@pytest.mark.parametrize("event_type", ["job.expired", "job.removed"])
def test_job_retirement_removes_prior_pair_results(event_type):
    fixtures = load_fixtures()
    jobs = MemoryJobs(fixtures.jobs)
    matches = MemoryMatches()
    harness = FixtureMatchHarness(
        MemoryProfiles(fixtures.profiles), jobs, matches, FixtureMatcher(fixtures), NOW
    )
    harness.handle(fixtures.events[0])
    retired = fixtures.jobs[1].model_copy(update={"content_version": 2, "active": False})
    event = fixtures.events[1].model_copy(
        update={"event_id": "event-retired", "event_type": event_type, "job_version": 2}
    )
    jobs.save_with_event(retired, event)
    assert harness.handle(event) == []
    assert [m.job_id for m in matches.list_for_candidate("candidate-demo", 1)] == ["job-demo-1"]
