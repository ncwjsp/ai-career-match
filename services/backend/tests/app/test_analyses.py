"""The upload-to-results lifecycle a browser polls."""

import pytest

from app.contracts.models import ErrorDetail
from app.core.errors import ConflictError, NotFound
from app.db.app.analyses import SqlAnalysisRepository
from app.db.app.sessions import SqlSessionStore


@pytest.fixture
def analyses(app_session_factory, clock):
    return SqlAnalysisRepository(app_session_factory, clock)


@pytest.fixture
def candidate(app_session_factory, clock):
    return SqlSessionStore(app_session_factory, clock).start()[1]


def error() -> ErrorDetail:
    return ErrorDetail(
        code="EXTRACTION_FAILED",
        message="The file could not be read.",
        retryable=False,
        request_id="req-1",
    )


def test_a_new_run_starts_queued(analyses, candidate):
    run = analyses.create("an-1", candidate, "resume-1")
    assert (run.state, run.result_count, run.error) == ("queued", 0, None)


def test_a_run_progresses_to_ready_with_its_result_count(analyses, candidate):
    analyses.create("an-1", candidate, "resume-1")
    analyses.advance("an-1", "extracting")
    analyses.advance("an-1", "profiling")
    analyses.advance("an-1", "matching", corpus_snapshot="corpus-2026-09-05")
    run = analyses.advance("an-1", "ready", result_count=5)
    assert (run.state, run.result_count) == ("ready", 5)
    assert run.corpus_snapshot == "corpus-2026-09-05"


def test_a_late_task_cannot_drag_a_finished_run_backwards(analyses, candidate):
    analyses.create("an-1", candidate, "resume-1")
    analyses.advance("an-1", "ready", result_count=3)
    assert analyses.advance("an-1", "extracting").state == "ready"


def test_a_failed_run_reports_its_error_and_stays_failed(analyses, candidate):
    analyses.create("an-1", candidate, "resume-1")
    run = analyses.fail("an-1", error())
    assert run.state == "failed"
    assert run.error.code == "EXTRACTION_FAILED"
    with pytest.raises(ConflictError):
        analyses.advance("an-1", "ready")


def test_warnings_accumulate(analyses, candidate):
    analyses.create("an-1", candidate, "resume-1")
    analyses.advance("an-1", "extracting", warnings=["No education section found."])
    run = analyses.advance("an-1", "profiling", warnings=["Experience dates overlap."])
    assert len(run.warnings) == 2


def test_an_unknown_run_is_not_found(analyses):
    assert analyses.get("an-missing") is None
    with pytest.raises(NotFound):
        analyses.advance("an-missing", "ready")
