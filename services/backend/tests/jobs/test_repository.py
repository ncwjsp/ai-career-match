"""`SqlJobRepository` behavior against a migrated `career_jobs` schema. Owner: M2 (B-09)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.jobs.repository import JobEventConflict, JobVersionConflict
from tests.jobs.factories import make_event, make_job

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def test_get_returns_none_for_unknown_job(job_repository):
    assert job_repository.get("missing") is None


def test_save_with_event_persists_job_and_outbox_event(job_repository):
    job = make_job()
    event = make_event()

    job_repository.save_with_event(job, event)

    assert job_repository.get("job-1") == job
    assert job_repository.get("job-1", version=1) == job
    pending = job_repository.pending()
    assert [e.event_id for e in pending] == ["event-1"]
    assert pending[0] == event


def test_job_and_event_versions_must_match():
    job = make_job(content_version=1)
    mismatched_event = make_event(job_version=2)

    from app.db.jobs.repository import SqlJobRepository

    with pytest.raises(ValueError, match="must match"):
        SqlJobRepository(None).save_with_event(job, mismatched_event)


def test_unchanged_reimport_is_idempotent_and_creates_no_duplicate_event(job_repository):
    job = make_job()
    event = make_event()

    job_repository.save_with_event(job, event)
    job_repository.save_with_event(job, event)  # Re-delivery of the identical event.

    assert len(job_repository.pending()) == 1
    assert job_repository.get("job-1") == job


def test_reused_event_id_with_different_body_is_rejected(job_repository):
    job = make_job()
    job_repository.save_with_event(job, make_event(event_id="event-1"))

    conflicting = make_event(event_id="event-1", occurred_at=NOW + timedelta(hours=1))
    with pytest.raises(JobEventConflict):
        job_repository.save_with_event(job, conflicting)


def test_reused_content_version_with_different_content_is_rejected(job_repository):
    job = make_job(content_version=1, title="NLP engineer")
    job_repository.save_with_event(job, make_event(event_id="event-1"))

    changed_same_version = make_job(content_version=1, title="Different title")
    with pytest.raises(JobVersionConflict):
        job_repository.save_with_event(changed_same_version, make_event(event_id="event-2"))


def test_changed_update_creates_new_version_and_keeps_the_previous_one(job_repository):
    v1 = make_job(content_version=1, title="NLP engineer")
    v2 = make_job(content_version=2, title="Senior NLP engineer")

    job_repository.save_with_event(v1, make_event(event_id="event-1", job_version=1))
    job_repository.save_with_event(
        v2, make_event(event_id="event-2", job_version=2, event_type="job.updated")
    )

    assert job_repository.get("job-1") == v2  # latest by default
    assert job_repository.get("job-1", version=1) == v1  # prior version still readable
    assert {e.event_id for e in job_repository.pending()} == {"event-1", "event-2"}


def test_list_active_excludes_inactive_and_expired_jobs(job_repository):
    active = make_job(job_id="job-active", active=True)
    inactive = make_job(job_id="job-inactive", active=False)
    expired = make_job(job_id="job-expired", active=True, expires_at=NOW - timedelta(days=1))
    not_yet_expired = make_job(job_id="job-fresh", active=True, expires_at=NOW + timedelta(days=1))

    for i, job in enumerate([active, inactive, expired, not_yet_expired]):
        job_repository.save_with_event(job, make_event(job_id=job.job_id, event_id=f"e{i}"))

    result_ids = {job.job_id for job in job_repository.list_active(NOW)}
    assert result_ids == {"job-active", "job-fresh"}


def test_list_active_uses_the_latest_version_only(job_repository):
    v1 = make_job(content_version=1, active=True)
    v2 = make_job(content_version=2, active=False)  # e.g. later closed

    job_repository.save_with_event(v1, make_event(event_id="event-1", job_version=1))
    job_repository.save_with_event(
        v2, make_event(event_id="event-2", job_version=2, event_type="job.updated")
    )

    assert job_repository.list_active(NOW) == []


def test_acknowledge_removes_event_from_pending(job_repository):
    job_repository.save_with_event(make_job(), make_event())

    job_repository.acknowledge("event-1")

    assert job_repository.pending() == []


def test_acknowledge_unknown_event_is_a_no_op(job_repository):
    job_repository.acknowledge("does-not-exist")  # Must not raise.


def test_pending_respects_limit_and_fifo_order(job_repository):
    for i in range(3):
        job = make_job(job_id=f"job-{i}")
        job_repository.save_with_event(job, make_event(job_id=f"job-{i}", event_id=f"event-{i}"))

    first_two = job_repository.pending(limit=2)
    assert [e.event_id for e in first_two] == ["event-0", "event-1"]


def test_save_with_event_rolls_back_on_failure_before_commit(
    job_repository, job_session_factory, monkeypatch
):
    """A crash between staging writes and commit must leave no trace (B-09 evidence)."""

    def failing_commit(self):
        raise RuntimeError("simulated crash before commit")

    monkeypatch.setattr(Session, "commit", failing_commit)
    with pytest.raises(RuntimeError, match="simulated crash"):
        job_repository.save_with_event(make_job(), make_event())
    monkeypatch.undo()

    assert job_repository.get("job-1") is None
    assert job_repository.pending() == []
