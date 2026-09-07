"""Job source registration and manual import-run/check metadata. Owner: M2 (B-09)."""

from datetime import UTC, datetime

import pytest


def test_register_creates_then_updates_a_source(job_source_repository):
    created = job_source_repository.register(
        "src-1", "Example Careers", "https://careers.example.test", "career_page", True
    )
    assert created.permitted is True

    updated = job_source_repository.register(
        "src-1",
        "Example Careers",
        "https://careers.example.test",
        "career_page",
        False,
        permitted_notes="robots.txt now disallows /jobs",
    )
    assert updated.permitted is False
    assert job_source_repository.get("src-1").permitted_notes == "robots.txt now disallows /jobs"
    assert [s.source_id for s in job_source_repository.list()] == ["src-1"]


def test_mark_checked_records_the_last_check_time(job_source_repository):
    job_source_repository.register(
        "src-1", "Example Careers", "https://careers.example.test", "career_page", True
    )
    checked_at = datetime(2026, 9, 5, tzinfo=UTC)

    job_source_repository.mark_checked("src-1", checked_at)

    assert job_source_repository.get("src-1").checked_at == checked_at


def test_import_run_lifecycle_success(job_import_run_repository):
    run = job_import_run_repository.start("run-1", "https://jobs.example.test/job-1")
    assert run.status == "queued"

    completed = job_import_run_repository.complete("run-1", "success", job_id="job-1")

    assert completed.status == "success"
    assert completed.job_id == "job-1"
    assert completed.finished_at is not None


def test_import_run_lifecycle_failure_preserves_error(job_import_run_repository):
    job_import_run_repository.start("run-1", "https://jobs.example.test/job-1")

    completed = job_import_run_repository.complete(
        "run-1", "failed", error_message="Unsupported source"
    )

    assert completed.status == "failed"
    assert completed.error_message == "Unsupported source"


def test_complete_rejects_unknown_status(job_import_run_repository):
    job_import_run_repository.start("run-1", "https://jobs.example.test/job-1")
    with pytest.raises(ValueError):
        job_import_run_repository.complete("run-1", "queued")


def test_complete_unknown_run_raises(job_import_run_repository):
    with pytest.raises(LookupError):
        job_import_run_repository.complete("missing", "success")


def test_last_successful_check_prefers_most_recent_success_or_unchanged(
    job_import_run_repository,
):
    url = "https://jobs.example.test/job-1"
    job_import_run_repository.start("run-1", url)
    job_import_run_repository.complete("run-1", "success")
    job_import_run_repository.start("run-2", url)
    job_import_run_repository.complete("run-2", "failed", error_message="timeout")
    job_import_run_repository.start("run-3", url)
    third = job_import_run_repository.complete("run-3", "unchanged")

    last_check = job_import_run_repository.last_successful_check(url)

    assert last_check == third.finished_at


def test_last_successful_check_is_none_when_never_checked(job_import_run_repository):
    assert job_import_run_repository.last_successful_check("https://jobs.example.test/x") is None


def test_raw_snapshot_round_trip(job_import_run_repository, job_raw_snapshot_repository):
    job_import_run_repository.start("run-1", "https://jobs.example.test/job-1")

    job_raw_snapshot_repository.save(
        "snap-1",
        "run-1",
        "https://jobs.example.test/job-1",
        datetime(2026, 9, 5, tzinfo=UTC),
        "text/html",
        "deadbeef",
        "<html>raw job posting</html>",
    )

    assert job_raw_snapshot_repository.get("snap-1") == "<html>raw job posting</html>"
    assert job_raw_snapshot_repository.get("missing") is None
