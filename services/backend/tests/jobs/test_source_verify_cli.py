"""verify_cli's own logic (B-01). The transport is monkeypatched; no network."""

import app.modules.jobs.sources.verify_cli as verify_cli
from app.modules.jobs.sources.fetch import SourceFetchError


class FakeTransport:
    def __init__(self, responses: dict[str, tuple[int, str, bytes]]):
        self._responses = responses
        self.calls: list[str] = []

    def get(self, url: str, *, timeout: float):
        self.calls.append(url)
        if url not in self._responses:
            raise SourceFetchError(f"unexpected URL in test: {url}")
        return self._responses[url]


def _patch_transport(monkeypatch, transport):
    monkeypatch.setattr(verify_cli, "UrllibTransport", lambda: transport)


def test_reports_allowed_when_robots_txt_permits_the_path(monkeypatch, capsys):
    transport = FakeTransport(
        {
            "https://jobs.example.test/robots.txt": (
                200,
                "text/plain",
                b"User-agent: *\nDisallow: /admin/\n",
            )
        }
    )
    _patch_transport(monkeypatch, transport)

    exit_code = verify_cli.main(["https://jobs.example.test", "--path", "/posting/1"])

    assert exit_code == 0
    assert "can_fetch" in capsys.readouterr().out
    assert transport.calls == ["https://jobs.example.test/robots.txt"]


def test_a_missing_robots_txt_is_treated_as_no_rules_not_a_failure(monkeypatch, capsys):
    transport = FakeTransport(
        {"https://jobs.example.test/robots.txt": (404, "text/html", b"not found")}
    )
    _patch_transport(monkeypatch, transport)

    exit_code = verify_cli.main(["https://jobs.example.test", "--path", "/posting/1"])

    assert exit_code == 0
    assert "can_fetch" in capsys.readouterr().out


def test_a_robots_txt_fetch_failure_exits_nonzero(monkeypatch, capsys):
    class ExplodingTransport:
        def get(self, url, *, timeout):
            raise SourceFetchError("dns lookup failed")

    _patch_transport(monkeypatch, ExplodingTransport())

    exit_code = verify_cli.main(["https://jobs.example.test"])

    assert exit_code == 1
    assert "FAILED" in capsys.readouterr().err


def test_an_unparseable_base_url_exits_nonzero(capsys):
    exit_code = verify_cli.main(["not-a-url"])

    assert exit_code == 2
    assert "Could not parse" in capsys.readouterr().err


def test_fetch_sample_reports_the_real_retrieval_evidence(monkeypatch, capsys):
    transport = FakeTransport(
        {
            "https://jobs.example.test/robots.txt": (200, "text/plain", b"User-agent: *\n"),
            "https://jobs.example.test/posting/1": (200, "text/html", b"<html>a posting</html>"),
        }
    )
    _patch_transport(monkeypatch, transport)

    exit_code = verify_cli.main(
        [
            "https://jobs.example.test",
            "--fetch-sample",
            "https://jobs.example.test/posting/1",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "HTTP 200" in out
    assert "real retrieval" in out


def test_fetch_sample_failure_exits_nonzero(monkeypatch, capsys):
    transport = FakeTransport(
        {"https://jobs.example.test/robots.txt": (200, "text/plain", b"User-agent: *\n")}
    )
    _patch_transport(monkeypatch, transport)

    exit_code = verify_cli.main(
        [
            "https://jobs.example.test",
            "--fetch-sample",
            "https://jobs.example.test/missing",
        ]
    )

    assert exit_code == 1
