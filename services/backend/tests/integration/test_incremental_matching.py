"""C-08: a new job refreshes retained candidates with the browser closed.

This is the local half of the INT-01 gate. Jobs live in M2's `career_jobs`
double; candidates, queues and published revisions live in the real `career_app`
schema. No test here uploads a second resume or calls a parser.
"""

import pytest

from app.contracts.models import ReconciliationEvent
from tests.app.factories import job_change, make_profile, profile_ready
from tests.integration.fakes import FlakyQueue
from tests.jobs.factories import make_job


@pytest.fixture
def candidate(wiring):
    """One retained candidate whose resume was parsed once, a week ago."""
    _, candidate_id = wiring["sessions"].start()
    wiring["profiles"].save(make_profile(candidate_id))
    return candidate_id


def import_job(wiring, job_id="job-1", version=1, event_type="job.created", **kwargs):
    """What a successful manual URL import commits in career_jobs."""
    job = make_job(job_id, version, fetched_at=wiring["clock"].now(), **kwargs)
    wiring["jobs"].save_with_event(job, job_change(job_id, version, event_type))
    return job


def test_a_new_job_refreshes_a_retained_candidate_without_a_second_upload(wiring, candidate):
    import_job(wiring, "job-1")
    wiring["worker"].run_until_idle()
    first = wiring["recommendations"].latest(candidate)
    assert [r.job_id for r in first.results] == ["job-1"]

    # The browser is closed. A team member imports another job.
    import_job(wiring, "job-2")
    wiring["worker"].run_until_idle()

    latest = wiring["recommendations"].latest(candidate)
    assert latest.revision == first.revision + 1
    assert [r.job_id for r in latest.results] == ["job-2", "job-1"]  # 84.0 then 77.0
    assert latest.profile_version == 1  # The same parsed profile, not a new one.


def test_the_profile_ready_trigger_scores_the_existing_corpus(wiring):
    import_job(wiring, "job-1")
    import_job(wiring, "job-2")
    wiring["worker"].run_until_idle()

    # A candidate arrives after the jobs are already stored.
    _, candidate_id = wiring["sessions"].start()
    wiring["profiles"].save(make_profile(candidate_id))
    wiring["queue"].enqueue(profile_ready(candidate_id))
    wiring["worker"].run_until_idle()

    latest = wiring["recommendations"].latest(candidate_id)
    assert [r.job_id for r in latest.results] == ["job-2", "job-1"]
    assert [r.rank for r in latest.results] == [1, 2]


def test_both_triggers_use_the_same_score_for_a_pair(wiring, candidate):
    import_job(wiring, "job-1")
    wiring["worker"].run_until_idle()
    by_job_event = wiring["recommendations"].latest(candidate).results[0].score

    _, other = wiring["sessions"].start()
    wiring["profiles"].save(make_profile(other))
    wiring["queue"].enqueue(profile_ready(other))
    wiring["worker"].run_until_idle()
    by_profile_event = wiring["recommendations"].latest(other).results[0].score

    assert by_job_event == by_profile_event == 77.0


def test_a_redelivered_job_event_creates_no_duplicate_match_or_revision(wiring, candidate):
    job = import_job(wiring, "job-1")
    wiring["worker"].run_until_idle()
    revision = wiring["recommendations"].latest(candidate).revision

    # M2's outbox redelivers the same committed event after a crash.
    wiring["jobs"].save_with_event(job, job_change("job-1", 1))
    wiring["worker"].run_until_idle()

    assert wiring["matches"].count_for_candidate(candidate, 1) == 1
    assert wiring["recommendations"].latest(candidate).revision == revision


def test_an_unchanged_republication_does_not_churn_revisions(wiring, candidate):
    import_job(wiring, "job-1")
    wiring["worker"].run_until_idle()
    revision = wiring["recommendations"].latest(candidate).revision

    wiring["queue"].enqueue(
        ReconciliationEvent(
            event_id="evt-reconcile-1",
            event_type="reconciliation.requested",
            occurred_at=wiring["clock"].now(),
        )
    )
    wiring["worker"].run_until_idle()
    assert wiring["recommendations"].latest(candidate).revision == revision


def test_an_updated_job_publishes_a_new_revision_with_the_new_version(wiring, candidate):
    import_job(wiring, "job-1", 1)
    wiring["worker"].run_until_idle()

    import_job(wiring, "job-1", 2, event_type="job.updated", title="Senior NLP engineer")
    wiring["worker"].run_until_idle()

    latest = wiring["recommendations"].latest(candidate)
    assert latest.revision == 2
    assert [(r.job_id, r.job_version) for r in latest.results] == [("job-1", 2)]


def test_an_event_for_a_superseded_version_is_skipped(wiring, candidate):
    import_job(wiring, "job-1", 1)
    import_job(wiring, "job-1", 2, event_type="job.updated")
    # Both events are queued; the one for version 1 is already obsolete.
    wiring["worker"].run_until_idle()
    latest = wiring["recommendations"].latest(candidate)
    assert [(r.job_id, r.job_version) for r in latest.results] == [("job-1", 2)]


def test_a_score_for_a_superseded_job_version_is_not_published(wiring, candidate):
    import_job(wiring, "job-1", 1)
    wiring["worker"].run_until_idle()
    import_job(wiring, "job-1", 2, event_type="job.updated")
    wiring["worker"].run_until_idle()
    # Both versions are stored as separate scores; only the current one is shown.
    assert wiring["matches"].count_for_candidate(candidate, 1) == 2
    assert len(wiring["recommendations"].latest(candidate).results) == 1


def test_an_expired_job_is_dropped_from_the_published_ranking(wiring, candidate):
    import_job(wiring, "job-1")
    import_job(wiring, "job-2")
    wiring["worker"].run_until_idle()
    assert len(wiring["recommendations"].latest(candidate).results) == 2

    import_job(wiring, "job-1", 2, event_type="job.expired", active=False)
    wiring["worker"].run_until_idle()

    latest = wiring["recommendations"].latest(candidate)
    assert [r.job_id for r in latest.results] == ["job-2"]


def test_an_expired_candidate_stops_receiving_revisions(wiring, candidate):
    import_job(wiring, "job-1")
    wiring["worker"].run_until_idle()
    revision = wiring["recommendations"].latest(candidate).revision

    wiring["clock"].advance(60 * 60 * 24 * 31)  # Past the retention window.
    import_job(wiring, "job-2")
    wiring["worker"].run_until_idle()

    assert wiring["recommendations"].latest(candidate).revision == revision


def test_a_candidate_who_disabled_matching_stops_receiving_revisions(wiring, candidate):
    import_job(wiring, "job-1")
    wiring["worker"].run_until_idle()
    revision = wiring["recommendations"].latest(candidate).revision

    wiring["profiles"].set_matching_enabled(candidate, False)
    import_job(wiring, "job-2")
    wiring["worker"].run_until_idle()

    assert wiring["recommendations"].latest(candidate).revision == revision


def test_one_job_event_matches_every_retained_candidate_in_batches(wiring):
    candidates = []
    for _ in range(5):  # batch_size is 2 in this wiring
        _, candidate_id = wiring["sessions"].start()
        wiring["profiles"].save(make_profile(candidate_id))
        candidates.append(candidate_id)

    import_job(wiring, "job-1")
    wiring["worker"].run_until_idle()

    for candidate_id in candidates:
        assert wiring["recommendations"].latest(candidate_id).results[0].job_id == "job-1"
    assert len(wiring["matcher"].pair_calls) == 5


def test_a_crashed_run_resumes_from_its_checkpoint(wiring):
    for _ in range(4):
        _, candidate_id = wiring["sessions"].start()
        wiring["profiles"].save(make_profile(candidate_id))
    import_job(wiring, "job-1")

    boom = RuntimeError("worker killed")

    class HalfwayMatcher:
        """Scores the first batch, then dies, like a process being terminated."""

        def __init__(self, real):
            self.real = real
            self.batches = 0

        def match_job(self, job, profiles, scoring_version):
            self.batches += 1
            if self.batches == 2:
                raise boom
            return self.real.match_job(job, profiles, scoring_version)

        def score_pair(self, *args):
            return self.real.score_pair(*args)

    wiring["service"]._matcher = HalfwayMatcher(wiring["matcher"])
    with pytest.raises(RuntimeError):
        wiring["service"].handle(job_change("job-1", 1))

    run = wiring["runs"].by_event("evt-job.created-job-1-1")
    assert run.state == "failed"
    assert run.checkpoint is not None  # The first batch was recorded.

    # The retry resumes after the checkpoint instead of rescoring from scratch.
    scored_before_the_crash = len(wiring["matcher"].pair_calls)
    wiring["service"]._matcher = wiring["matcher"]
    wiring["service"].handle(job_change("job-1", 1))
    remaining = len(wiring["matcher"].pair_calls) - scored_before_the_crash
    assert remaining == 2  # Only the two candidates after the checkpoint.


def test_an_event_is_only_acknowledged_in_career_jobs_after_it_is_durable(wiring, candidate):
    import_job(wiring, "job-1")
    flaky = FlakyQueue(wiring["queue"], fail_on=1)
    dispatcher = type(wiring["dispatcher"])(wiring["jobs"], flaky)

    with pytest.raises(RuntimeError):
        dispatcher.dispatch_once()
    # career_jobs still holds the event, so nothing was lost.
    assert [e.event_id for e in wiring["jobs"].pending()] == ["evt-job.created-job-1-1"]

    assert dispatcher.dispatch_once() == 1
    assert wiring["jobs"].pending() == []
    wiring["worker"].run_until_idle()
    assert wiring["recommendations"].latest(candidate) is not None


def test_a_failing_handler_is_retried_then_parked(wiring, candidate):
    import_job(wiring, "job-1")

    class BrokenMatcher:
        def match_job(self, *args):
            raise RuntimeError("scoring unavailable")

    wiring["service"]._matcher = BrokenMatcher()
    for _ in range(3):
        wiring["worker"].run_until_idle(max_events=1)
        wiring["clock"].advance(30)

    assert wiring["queue"].maintenance.failed_events() == ["evt-job.created-job-1-1"]
    assert wiring["recommendations"].latest(candidate) is None


def test_the_resume_parser_is_never_called_during_a_job_refresh(wiring, candidate):
    # The wiring has no resume processor at all: MatchService cannot reach one.
    import_job(wiring, "job-1")
    wiring["worker"].run_until_idle()
    assert not hasattr(wiring["service"], "_resume_processor")
    assert wiring["recommendations"].latest(candidate) is not None
