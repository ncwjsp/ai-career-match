"""URL-based job import (B-02): fetch -> normalize -> hash-compare -> persist.

Runs against the real Alembic-migrated `career_jobs` SQLite schema (see
tests/jobs/conftest.py), with a fake HTTP transport -- no real network.
"""

from datetime import UTC, datetime

import pytest

from app.core.clock import FixedClock
from app.modules.jobs.ingest import JobIngestionService, UnsupportedSourceError
from app.modules.jobs.sources.fetch import SourceFetchError

NOW = datetime(2026, 9, 16, tzinfo=UTC)
ALLOWED = frozenset({"jobs.example.test"})
URL = "https://jobs.example.test/posting/1"

HTML_V1 = """
<html><head><title>ignored</title>
<script type="application/ld+json">
{"@type": "JobPosting", "title": "NLP Engineer",
 "hiringOrganization": {"name": "Example Labs"},
 "description": "Build things with Python and SQL."}
</script></head><body></body></html>
"""

HTML_V2 = """
<html><head><title>ignored</title>
<script type="application/ld+json">
{"@type": "JobPosting", "title": "Senior NLP Engineer",
 "hiringOrganization": {"name": "Example Labs"},
 "description": "Build things with Python, SQL, and Docker."}
</script></head><body></body></html>
"""


class FakeTransport:
    def __init__(self, responses: dict[str, tuple[int, str, bytes]] | None = None):
        self._responses = responses or {}

    def set(self, url: str, status: int, content_type: str, body: bytes) -> None:
        self._responses[url] = (status, content_type, body)

    def get(self, url: str, *, timeout: float):
        if url not in self._responses:
            raise SourceFetchError(f"unexpected URL in test: {url}")
        return self._responses[url]


class ExplodingTransport:
    def get(self, url: str, *, timeout: float):
        raise SourceFetchError("connection refused")


@pytest.fixture(autouse=True)
def _registered_source(job_source_repository):
    """`job_import_runs.source_id` is a foreign key into `job_sources`; every
    test here imports as this pre-registered fixture source."""
    job_source_repository.register(
        "fixture-source", "Fixture Source", "https://jobs.example.test", "fixture", True
    )


@pytest.fixture
def make_service(job_repository, job_import_run_repository, job_raw_snapshot_repository):
    def build(transport) -> JobIngestionService:
        return JobIngestionService(
            job_repository,
            job_import_run_repository,
            job_raw_snapshot_repository,
            allowed_hosts=ALLOWED,
            source_id="fixture-source",
            transport=transport,
            clock=FixedClock(NOW),
        )

    return build


def test_a_first_import_creates_a_new_job_with_one_event(
    make_service, job_repository, job_import_run_repository
):
    service = make_service(FakeTransport({URL: (200, "text/html", HTML_V1.encode())}))

    report = service.import_url(URL)

    assert (report.new_jobs, report.changed_jobs, report.unchanged_jobs) == (1, 0, 0)
    assert len(report.event_ids) == 1
    run = job_import_run_repository.get(report.run_id)
    assert run.status == "success"
    assert run.job_id is not None

    stored = job_repository.get(run.job_id)
    assert stored.title == "NLP Engineer"
    assert stored.company == "Example Labs"
    assert stored.content_version == 1


def test_reimporting_unchanged_content_emits_no_new_event(
    make_service, job_repository, job_import_run_repository
):
    service = make_service(FakeTransport({URL: (200, "text/html", HTML_V1.encode())}))
    first = service.import_url(URL)

    second = service.import_url(URL)

    assert (second.new_jobs, second.changed_jobs, second.unchanged_jobs) == (0, 0, 1)
    assert second.event_ids == []
    run = job_import_run_repository.get(second.run_id)
    assert run.status == "unchanged"
    stored = job_repository.get(job_import_run_repository.get(first.run_id).job_id)
    assert stored.content_version == 1  # no new version was written


def test_reimporting_changed_content_bumps_the_version_and_emits_job_updated(
    make_service, job_repository, job_import_run_repository
):
    transport = FakeTransport({URL: (200, "text/html", HTML_V1.encode())})
    service = make_service(transport)
    first = service.import_url(URL)
    job_id = job_import_run_repository.get(first.run_id).job_id

    transport.set(URL, 200, "text/html", HTML_V2.encode())
    second = service.import_url(URL)

    assert (second.new_jobs, second.changed_jobs, second.unchanged_jobs) == (0, 1, 0)
    assert len(second.event_ids) == 1
    stored = job_repository.get(job_id)
    assert stored.content_version == 2
    assert stored.title == "Senior NLP Engineer"


def test_a_fetch_failure_records_a_failed_run_and_touches_no_job_data(
    make_service, job_repository, job_import_run_repository
):
    service = make_service(FakeTransport({URL: (200, "text/html", HTML_V1.encode())}))
    first = service.import_url(URL)
    job_id = job_import_run_repository.get(first.run_id).job_id

    failing_service = make_service(ExplodingTransport())
    report = failing_service.import_url(URL)

    assert (report.new_jobs, report.changed_jobs, report.unchanged_jobs) == (0, 0, 0)
    assert report.event_ids == []
    assert report.warnings
    run = job_import_run_repository.get(report.run_id)
    assert run.status == "failed"
    stored = job_repository.get(job_id)
    assert stored.content_version == 1  # prior data untouched
    assert stored.title == "NLP Engineer"


def test_a_disallowed_host_raises_before_any_fetch(make_service):
    service = make_service(FakeTransport())

    with pytest.raises(UnsupportedSourceError):
        service.import_url("https://not-approved.example.test/posting/1")


def test_a_non_https_url_raises(make_service):
    service = make_service(FakeTransport())

    with pytest.raises(UnsupportedSourceError):
        service.import_url("http://jobs.example.test/posting/1")


def test_query_string_variants_of_the_same_url_share_one_job_id(
    make_service, job_import_run_repository
):
    with_query = f"{URL}?ref=email"
    transport = FakeTransport(
        {
            URL: (200, "text/html", HTML_V1.encode()),
            with_query: (200, "text/html", HTML_V1.encode()),
        }
    )
    service = make_service(transport)

    first = service.import_url(URL)
    second = service.import_url(with_query)

    job_id = job_import_run_repository.get(first.run_id).job_id
    assert job_import_run_repository.get(second.run_id).job_id == job_id
    assert (second.new_jobs, second.changed_jobs, second.unchanged_jobs) == (0, 0, 1)


def test_mark_closed_flips_active_and_emits_job_expired(
    make_service, job_repository, job_import_run_repository
):
    service = make_service(FakeTransport({URL: (200, "text/html", HTML_V1.encode())}))
    first = service.import_url(URL)
    job_id = job_import_run_repository.get(first.run_id).job_id

    closed = service.mark_closed(job_id)

    assert closed.active is False
    assert closed.content_version == 2
    stored = job_repository.get(job_id)
    assert stored.active is False
    assert stored.content_version == 2


def test_mark_closed_twice_is_a_no_op_the_second_time(make_service, job_import_run_repository):
    service = make_service(FakeTransport({URL: (200, "text/html", HTML_V1.encode())}))
    first = service.import_url(URL)
    job_id = job_import_run_repository.get(first.run_id).job_id
    service.mark_closed(job_id)

    second_close = service.mark_closed(job_id)

    assert second_close.content_version == 2  # unchanged: still the first closure's version


def test_mark_closed_on_an_unknown_job_returns_none(make_service):
    service = make_service(FakeTransport())

    assert service.mark_closed("job-does-not-exist") is None


def test_each_import_is_attributed_to_its_own_hosts_source(
    job_repository, job_import_run_repository, job_raw_snapshot_repository, job_source_repository
):
    job_source_repository.register(
        "second-source", "Second Source", "https://jobs.second.test", "fixture", True
    )
    second_url = "https://jobs.second.test/posting/9"
    service = JobIngestionService(
        job_repository,
        job_import_run_repository,
        job_raw_snapshot_repository,
        allowed_hosts=frozenset({"jobs.example.test", "jobs.second.test"}),
        source_id="fixture-source",
        source_ids_by_host={"jobs.second.test": "second-source"},
        transport=FakeTransport(
            {
                URL: (200, "text/html", HTML_V1.encode()),
                second_url: (200, "text/html", HTML_V2.encode()),
            }
        ),
        clock=FixedClock(NOW),
    )

    first = service.import_url(URL)
    second = service.import_url(second_url)

    first_run = job_import_run_repository.get(first.run_id)
    second_run = job_import_run_repository.get(second.run_id)
    assert job_repository.get(first_run.job_id).source_id == "fixture-source"
    assert job_repository.get(second_run.job_id).source_id == "second-source"
    assert second_run.source_id == "second-source"
