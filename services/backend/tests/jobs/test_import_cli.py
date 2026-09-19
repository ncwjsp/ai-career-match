"""import_cli's own wiring (B-02/B-07 tool). Transport is monkeypatched; no
network. Real Alembic-migrated SQLite via the job_db_url fixture."""

import app.modules.jobs.import_cli as import_cli
from app.modules.jobs.sources.fetch import SourceFetchError

URL = "https://job-boards.greenhouse.io/example/jobs/1"

HTML = """
<html><head><title>ignored</title>
<script type="application/ld+json">
{"@type": "JobPosting", "title": "NLP Engineer",
 "hiringOrganization": {"name": "Example Labs"},
 "description": "Build things with Python."}
</script></head><body></body></html>
"""


class FakeTransport:
    def __init__(self, responses):
        self._responses = responses

    def get(self, url: str, *, timeout: float):
        if url not in self._responses:
            raise SourceFetchError(f"unexpected URL in test: {url}")
        return self._responses[url]


def _patch_transport(monkeypatch, transport):
    import app.modules.jobs.sources.fetch as fetch_module

    monkeypatch.setattr(fetch_module, "UrllibTransport", lambda: transport)


def test_a_first_import_reports_a_new_job(job_db_url, monkeypatch, capsys):
    _patch_transport(monkeypatch, FakeTransport({URL: (200, "text/html", HTML.encode())}))

    exit_code = import_cli.main([URL])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "new_jobs=1" in out
    assert "Imported successfully" in out


def test_reimporting_unchanged_content_reports_no_change(job_db_url, monkeypatch, capsys):
    _patch_transport(monkeypatch, FakeTransport({URL: (200, "text/html", HTML.encode())}))
    import_cli.main([URL])

    exit_code = import_cli.main([URL])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "unchanged_jobs=1" in out
    assert "No change" in out


def test_a_disallowed_host_is_rejected_with_exit_code_2(job_db_url, capsys):
    exit_code = import_cli.main(["https://not-approved.example.test/jobs/1"])

    assert exit_code == 2
    assert "Rejected" in capsys.readouterr().err


def test_a_fetch_failure_exits_nonzero(job_db_url, monkeypatch, capsys):
    class ExplodingTransport:
        def get(self, url: str, *, timeout: float):
            raise SourceFetchError("connection refused")

    _patch_transport(monkeypatch, ExplodingTransport())

    exit_code = import_cli.main([URL])

    assert exit_code == 1
    assert "FAILED" in capsys.readouterr().err


def test_lever_and_ashby_urls_import_as_their_own_sources(job_db_url, monkeypatch, capsys):
    from app.core.settings import Settings
    from app.db.jobs.database import create_job_engine, session_factory
    from app.db.jobs.repository import SqlJobRepository
    from app.modules.jobs.ingest import _canonical_job_id, _canonicalize_url

    lever = "https://jobs.lever.co/example/0b1c2d3e-aaaa-bbbb-cccc-123456789abc"
    ashby = "https://jobs.ashbyhq.com/example/7458d4e9-da2e-47bd-98cb-adfda43d42b2"
    page = (200, "text/html", HTML.encode())
    _patch_transport(monkeypatch, FakeTransport({lever: page, ashby: page}))

    assert import_cli.main([lever]) == 0
    assert import_cli.main([ashby]) == 0

    jobs = SqlJobRepository(session_factory(create_job_engine(Settings())))
    for url, source_id in ((lever, "lever"), (ashby, "ashby")):
        assert jobs.get(_canonical_job_id(_canonicalize_url(url))).source_id == source_id
