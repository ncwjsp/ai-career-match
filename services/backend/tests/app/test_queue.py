"""Durable queue behavior: idempotency, leases, bounded retries, recovery."""

import pytest

from app.contracts.models import FileRef
from app.db.app.analyses import SqlAnalysisRepository
from app.db.app.queue import SqlAnalysisQueue, SqlMatchQueue, SqlProcessedEvents
from app.db.app.sessions import SqlSessionStore
from tests.app.factories import job_change, profile_ready


@pytest.fixture
def queue(app_session_factory, clock):
    return SqlMatchQueue(
        app_session_factory, clock, lease_seconds=300, max_attempts=3, backoff_seconds=30
    )


def test_an_accepted_event_is_claimed_once(queue):
    event = job_change()
    assert queue.enqueue(event) is True
    assert queue.claim() == event
    assert queue.claim() is None


def test_a_redelivered_event_is_not_queued_twice(queue):
    event = job_change()
    assert queue.enqueue(event) is True
    assert queue.enqueue(event) is False
    assert queue.claim() == event
    assert queue.claim() is None


def test_a_replay_after_completion_and_cleanup_is_still_ignored(queue):
    event = job_change()
    queue.enqueue(event)
    queue.claim()
    queue.acknowledge(event.event_id)
    assert queue.maintenance.purge_done() == 1
    # The queue row is gone, but processed_events still remembers the event.
    assert queue.enqueue(event) is False
    assert queue.claim() is None


def test_events_are_claimed_oldest_first(queue, clock):
    first = job_change("job-1")
    clock.advance(1)
    second = job_change("job-2")
    queue.enqueue(first)
    clock.advance(1)
    queue.enqueue(second)
    assert queue.claim().job_id == "job-1"
    assert queue.claim().job_id == "job-2"


def test_both_trigger_kinds_share_one_queue(queue):
    queue.enqueue(profile_ready())
    queue.enqueue(job_change())
    claimed = [queue.claim(), queue.claim()]
    assert {event.event_type for event in claimed} == {"profile.ready", "job.created"}


def test_a_crashed_worker_leaves_the_event_for_the_next_claim(queue, clock):
    event = job_change()
    queue.enqueue(event)
    assert queue.claim() == event  # This worker then dies without acknowledging.
    assert queue.claim() is None  # The lease is still held.
    clock.advance(301)
    assert queue.claim() == event  # Recovered after the lease expires.


def test_an_acknowledged_event_is_never_reclaimed(queue, clock):
    event = job_change()
    queue.enqueue(event)
    queue.claim()
    queue.acknowledge(event.event_id)
    clock.advance(10_000)
    assert queue.claim() is None
    assert queue.maintenance.counts() == {"done": 1}


def test_a_retry_waits_for_its_backoff_then_runs_again(queue, clock):
    event = job_change()
    queue.enqueue(event)
    queue.claim()
    queue.retry(event.event_id, "matcher unavailable")
    assert queue.claim() is None
    clock.advance(30)
    assert queue.claim() == event


def test_a_poison_event_is_parked_after_its_attempts_run_out(queue, clock):
    event = job_change()
    queue.enqueue(event)
    for _ in range(3):
        assert queue.claim() == event
        queue.retry(event.event_id, "still failing")
        clock.advance(30)
    assert queue.claim() is None
    assert queue.maintenance.failed_events() == [event.event_id]
    assert queue.maintenance.counts() == {"failed": 1}


def test_a_parked_event_stays_readable_with_its_last_error(queue, app_session_factory, clock):
    from app.db.app.models import WorkQueueRow

    event = job_change()
    queue.enqueue(event)
    for _ in range(3):
        queue.claim()
        queue.retry(event.event_id, "still failing")
        clock.advance(30)
    with app_session_factory() as session:
        row = session.get(WorkQueueRow, event.event_id)
    assert (row.state, row.last_error, row.attempts) == ("failed", "still failing", 3)


def test_acknowledging_an_unknown_event_is_harmless(queue):
    queue.acknowledge("evt-nothing")
    queue.retry("evt-nothing")


def test_processed_events_records_completion(app_session_factory, clock, queue):
    processed = SqlProcessedEvents(app_session_factory, clock)
    event = job_change()
    queue.enqueue(event)
    queue.claim()
    assert processed.seen(event.event_id) is False
    queue.acknowledge(event.event_id)
    assert processed.seen(event.event_id) is True


def test_the_analysis_queue_carries_the_run_and_its_stored_file(app_session_factory, clock):
    candidate = SqlSessionStore(app_session_factory, clock).start()[1]
    run = SqlAnalysisRepository(app_session_factory, clock).create("an-1", candidate, "resume-1")
    file = FileRef(object_key="resumes/resume-abc", media_type="application/pdf")
    queue = SqlAnalysisQueue(app_session_factory, clock)
    queue.enqueue(run, file)
    claimed = queue.claim()
    assert claimed == (run, file)
    queue.acknowledge("an-1")
    assert queue.claim() is None


def test_the_two_queues_do_not_see_each_others_work(app_session_factory, clock, queue):
    analysis = SqlAnalysisQueue(app_session_factory, clock)
    queue.enqueue(job_change())
    assert analysis.claim() is None
