"""URL-based job import: fetch, normalize, decide new/changed/unchanged, persist
atomically. Owner: M2 (B-02).

This is R04's "manually import an individual permitted job URL; re-import a
URL to update its posting" -- fetch via B-01's allow-listed
`fetch_single_posting`, extract structured fields (`normalize.py`), and use
B-09's `JobRepository.save_with_event` so a content version and its outbox
event land in one `career_jobs` transaction. Change detection reuses
`app.db.jobs.mapping.content_hash`: an unchanged re-import writes nothing to
`jobs`/`job_versions`/`job_change_events` and only records that the check
happened, satisfying "unchanged re-import emits no duplicate event." A fetch
failure only records a failed import run -- it never touches prior job data,
satisfying "failed checks preserve prior data."

Not wired to a router yet. `docs/integration/OWNERSHIP.md` and plan.md both
flag the import request/status wire contract (`JobImportRequest`/
`JobImportRun` DTOs, the team-only access guard for D09) as a small M3
follow-up to agree before integration -- the existing
`JobIngestor.run(source_id)` port in `app.contracts.interfaces` predates B-01
and was never meant to describe this URL flow either (plan.md section 3).
Building a router/DTO now would risk a second, competing shape instead of
waiting for that agreed one. `JobIngestionService.import_url`/`mark_closed`
below are the domain operations a future router calls.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from urllib.parse import urlparse, urlunparse

from app.contracts.interfaces import JobRepository
from app.contracts.models import IngestionReport, JobChangeEvent, JobPosting
from app.core.clock import Clock, SystemClock
from app.core.ids import new_id
from app.db.jobs.mapping import content_hash
from app.db.jobs.sources import SqlJobImportRunRepository, SqlJobRawSnapshotRepository
from app.modules.jobs.normalize import normalize_posting
from app.modules.jobs.sources.fetch import HttpTransport, SourceFetchError, fetch_single_posting
from app.modules.jobs.summary import summarize


class UnsupportedSourceError(Exception):
    """The URL is not HTTPS, or its host is not an approved job-posting source
    (docs/job-sources/REGISTER.md). Rejected before any fetch or import-run
    record is created -- this is a request validation error, not a failed
    attempt."""


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))


def _canonical_job_id(canonical_url: str) -> str:
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:24]
    return f"job-{digest}"


class JobIngestionService:
    def __init__(
        self,
        jobs: JobRepository,
        import_runs: SqlJobImportRunRepository,
        raw_snapshots: SqlJobRawSnapshotRepository,
        *,
        allowed_hosts: frozenset[str],
        source_id: str,
        source_ids_by_host: Mapping[str, str] | None = None,
        transport: HttpTransport | None = None,
        clock: Clock | None = None,
        id_factory: Callable[[str], str] = new_id,
    ):
        self._jobs = jobs
        self._import_runs = import_runs
        self._raw_snapshots = raw_snapshots
        self._allowed_hosts = allowed_hosts
        self._source_id = source_id
        self._source_ids_by_host = dict(source_ids_by_host or {})
        self._transport = transport
        self._clock = clock or SystemClock()
        self._id_factory = id_factory

    def import_url(self, url: str) -> IngestionReport:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self._allowed_hosts:
            raise UnsupportedSourceError(
                f"{url!r} is not an approved, HTTPS job-posting URL. "
                "See docs/job-sources/REGISTER.md for the approved list."
            )
        canonical_url = _canonicalize_url(url)
        job_id = _canonical_job_id(canonical_url)

        # One service serves several approved hosts; each import is attributed
        # to its own host's source, falling back to the configured default.
        source_id = self._source_ids_by_host.get(parsed.hostname, self._source_id)

        run_id = self._id_factory("run")
        self._import_runs.start(run_id, url, source_id=source_id)
        try:
            page = fetch_single_posting(url, self._allowed_hosts, transport=self._transport)
        except SourceFetchError as error:
            self._import_runs.complete(run_id, "failed", error_message=str(error))
            return IngestionReport(
                run_id=run_id,
                new_jobs=0,
                changed_jobs=0,
                unchanged_jobs=0,
                event_ids=[],
                warnings=[str(error)],
            )

        snapshot_id = self._id_factory("snap")
        raw_hash = hashlib.sha256(page.body.encode("utf-8")).hexdigest()
        self._raw_snapshots.save(
            snapshot_id=snapshot_id,
            run_id=run_id,
            source_url=url,
            fetched_at=page.fetched_at,
            media_type=page.content_type,
            content_hash=raw_hash,
            raw_content=page.body,
        )

        normalized = normalize_posting(page.body, document_id=job_id, fetched_at=page.fetched_at)
        existing = self._jobs.get(job_id)
        next_version = (existing.content_version + 1) if existing else 1

        candidate = JobPosting(
            job_id=job_id,
            source_id=source_id,
            source_url=canonical_url,
            content_version=next_version,
            title=normalized.title,
            company=normalized.company,
            description=normalized.description,
            summary=summarize(normalized.description),
            requirements=normalized.requirements,
            other_requirements=normalized.other_requirements,
            evidence=normalized.evidence,
            language=normalized.language,
            fetched_at=page.fetched_at,
            last_seen_at=page.fetched_at,
            posted_at=normalized.posted_at,
            expires_at=normalized.expires_at,
            active=True,
            data_origin="permitted_source",
        )

        if existing is not None and content_hash(candidate) == content_hash(existing):
            self._import_runs.complete(run_id, "unchanged", job_id=job_id)
            return IngestionReport(
                run_id=run_id,
                new_jobs=0,
                changed_jobs=0,
                unchanged_jobs=1,
                event_ids=[],
                warnings=[],
            )

        event = JobChangeEvent(
            event_id=self._id_factory("evt"),
            event_type="job.created" if existing is None else "job.updated",
            job_id=job_id,
            job_version=next_version,
            occurred_at=self._clock.now(),
            content_ref=f"{job_id}@{next_version}",
        )
        self._jobs.save_with_event(candidate, event)
        self._import_runs.complete(run_id, "success", job_id=job_id)

        if existing is None:
            return IngestionReport(
                run_id=run_id,
                new_jobs=1,
                changed_jobs=0,
                unchanged_jobs=0,
                event_ids=[event.event_id],
                warnings=[],
            )
        return IngestionReport(
            run_id=run_id,
            new_jobs=0,
            changed_jobs=1,
            unchanged_jobs=0,
            event_ids=[event.event_id],
            warnings=[],
        )

    def mark_closed(self, job_id: str) -> JobPosting | None:
        """Manual "mark unavailable" action: flips `active` off as a new version
        with a `job.expired` event. A no-op (not another version) if the job is
        unknown or already closed."""
        existing = self._jobs.get(job_id)
        if existing is None or not existing.active:
            return existing
        next_version = existing.content_version + 1
        data = existing.model_dump()
        data.update(content_version=next_version, active=False, last_seen_at=self._clock.now())
        candidate = JobPosting.model_validate(data)
        event = JobChangeEvent(
            event_id=self._id_factory("evt"),
            event_type="job.expired",
            job_id=job_id,
            job_version=next_version,
            occurred_at=self._clock.now(),
            content_ref=f"{job_id}@{next_version}",
        )
        self._jobs.save_with_event(candidate, event)
        return candidate
