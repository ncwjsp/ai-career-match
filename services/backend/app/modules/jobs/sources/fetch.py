"""Bounded, single-URL fetch for one approved job-posting source. Owner: M2 (B-01).

Deliberately narrow: this is *not* B-02's general-purpose, SSRF-safe import
fetcher (redirect handling, private-IP/DNS-rebinding defenses, arbitrary
source support). This adapter only ever requests URLs on a host explicitly
passed in as `allowed_hosts` -- a closed allow-list, checked before any
request is made -- over HTTPS, with a bounded size and timeout. B-02
generalizes this into the manual-import flow's full safety requirements once
a source is actually approved; see docs/job-sources/REGISTER.md for which
one that is (as of this writing: none yet -- live verification is blocked in
the environment this was written in, see that file).

Uses the standard library only (`urllib.request`). `httpx` is already a
dev-only test dependency, but promoting it to a runtime dependency for one
bounded GET is a shared-manifest change to coordinate through M3, and nothing
here needs more than the standard library provides.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlparse

MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # A job posting page, not a video: 2 MiB is generous.
DEFAULT_TIMEOUT_SECONDS = 10.0
USER_AGENT = "ai-career-match-job-source/0.1 (+manual single-posting import)"


class SourceFetchError(Exception):
    """The URL was rejected, or the request failed. Never a partial/garbled body."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status_code: int
    content_type: str
    body: str
    fetched_at: datetime


class HttpTransport(Protocol):
    """What actually performs the request -- injectable so tests never touch
    the network, and so a different client can be substituted later without
    changing the allow-list/bounds logic below."""

    def get(self, url: str, *, timeout: float) -> tuple[int, str, bytes]:
        """Returns (status_code, content_type, body_bytes)."""
        ...


class UrllibTransport:
    """The default transport: the standard library, nothing more."""

    def get(self, url: str, *, timeout: float) -> tuple[int, str, bytes]:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                body = response.read(MAX_RESPONSE_BYTES + 1)
                return response.status, response.headers.get_content_type(), body
        except urllib.error.HTTPError as error:
            content_type = error.headers.get_content_type() if error.headers else ""
            return error.code, content_type, b""
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise SourceFetchError(f"Request to {url} failed: {error}") from error


def fetch_single_posting(
    url: str,
    allowed_hosts: frozenset[str],
    *,
    transport: HttpTransport | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    now: datetime | None = None,
) -> FetchedPage:
    """Fetch one job-posting URL from an explicitly permitted host.

    Rejects, before any request is made: a non-HTTPS URL, and any host not in
    `allowed_hosts`. A source only belongs in that set once it is genuinely
    approved (docs/job-sources/REGISTER.md) -- this function does not itself
    decide that; it enforces whatever the caller already decided.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SourceFetchError(f"Refusing a non-HTTPS URL: {url!r}")
    if parsed.hostname not in allowed_hosts:
        raise SourceFetchError(
            f"{parsed.hostname!r} is not an approved job-posting host. "
            "Add it to docs/job-sources/REGISTER.md and the caller's allow-list first."
        )
    client = transport or UrllibTransport()
    status, content_type, body = client.get(url, timeout=timeout)
    if len(body) > MAX_RESPONSE_BYTES:
        raise SourceFetchError(f"Response from {url} exceeded {MAX_RESPONSE_BYTES} bytes.")
    if status >= 400:
        raise SourceFetchError(f"{url} returned HTTP {status}.")
    return FetchedPage(
        url=url,
        status_code=status,
        content_type=content_type,
        body=body.decode("utf-8", errors="replace"),
        fetched_at=now or datetime.now(UTC),
    )
