"""Bounded single-URL fetch (B-01). No real network: HttpTransport is faked."""

from datetime import UTC, datetime

import pytest

from app.modules.jobs.sources.fetch import (
    MAX_RESPONSE_BYTES,
    SourceFetchError,
    fetch_single_posting,
)

NOW = datetime(2026, 9, 5, tzinfo=UTC)
ALLOWED = frozenset({"jobs.example.test"})


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@jobs.example.test/posting/1",
        "https://jobs.example.test:8080/posting/1",
        "https://jobs.example.test:invalid/posting/1",
    ],
)
def test_credentials_and_custom_ports_are_rejected(url):
    transport = FakeTransport()
    with pytest.raises(SourceFetchError):
        fetch_single_posting(url, ALLOWED, transport=transport)
    assert transport.calls == []


def test_redirect_response_is_not_imported_as_a_job():
    with pytest.raises(SourceFetchError, match="302"):
        fetch_single_posting(
            "https://jobs.example.test/posting/1", ALLOWED, transport=FakeTransport(status=302)
        )


class FakeTransport:
    def __init__(self, status=200, content_type="text/html", body=b"<html>a posting</html>"):
        self.status = status
        self.content_type = content_type
        self.body = body
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout: float):
        self.calls.append((url, timeout))
        return self.status, self.content_type, self.body


class ExplodingTransport:
    def get(self, url: str, *, timeout: float):
        raise SourceFetchError("connection refused")


def test_fetches_a_page_from_an_allowed_host():
    transport = FakeTransport()

    page = fetch_single_posting(
        "https://jobs.example.test/posting/1", ALLOWED, transport=transport, now=NOW
    )

    assert page.url == "https://jobs.example.test/posting/1"
    assert page.status_code == 200
    assert page.body == "<html>a posting</html>"
    assert page.fetched_at == NOW
    assert transport.calls == [("https://jobs.example.test/posting/1", 10.0)]


def test_rejects_a_non_https_url_before_any_request():
    transport = FakeTransport()

    with pytest.raises(SourceFetchError, match="HTTPS"):
        fetch_single_posting("http://jobs.example.test/posting/1", ALLOWED, transport=transport)
    assert transport.calls == []


def test_rejects_a_host_not_on_the_allow_list_before_any_request():
    transport = FakeTransport()

    with pytest.raises(SourceFetchError, match="not an approved"):
        fetch_single_posting("https://not-approved.test/posting/1", ALLOWED, transport=transport)
    assert transport.calls == []


def test_a_4xx_response_raises_rather_than_returning_an_error_page():
    transport = FakeTransport(status=404, body=b"not found")

    with pytest.raises(SourceFetchError, match="404"):
        fetch_single_posting("https://jobs.example.test/gone", ALLOWED, transport=transport)


def test_a_5xx_response_raises():
    transport = FakeTransport(status=503, body=b"")

    with pytest.raises(SourceFetchError, match="503"):
        fetch_single_posting("https://jobs.example.test/down", ALLOWED, transport=transport)


def test_an_oversized_response_is_rejected():
    transport = FakeTransport(body=b"x" * (MAX_RESPONSE_BYTES + 1))

    with pytest.raises(SourceFetchError, match="exceeded"):
        fetch_single_posting("https://jobs.example.test/huge", ALLOWED, transport=transport)


def test_a_transport_failure_becomes_a_source_fetch_error():
    with pytest.raises(SourceFetchError, match="connection refused"):
        fetch_single_posting(
            "https://jobs.example.test/posting/1", ALLOWED, transport=ExplodingTransport()
        )


def test_the_default_timeout_is_passed_to_the_transport():
    transport = FakeTransport()

    fetch_single_posting(
        "https://jobs.example.test/posting/1", ALLOWED, transport=transport, timeout=3.0
    )

    assert transport.calls == [("https://jobs.example.test/posting/1", 3.0)]


def test_a_non_utf8_body_is_decoded_leniently_not_raised():
    transport = FakeTransport(body=b"\xff\xfe not valid utf-8")

    page = fetch_single_posting("https://jobs.example.test/posting/1", ALLOWED, transport=transport)

    assert "not valid utf-8" in page.body
