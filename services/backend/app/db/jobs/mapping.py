"""Conversions between `JobPosting`/`JobChangeEvent` contracts and ORM rows.

Kept separate from `repository.py` so the row shape and the contract shape can
each change without the other having to be re-read line by line.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app.contracts.models import JobChangeEvent, JobPosting
from app.db.jobs.timeutil import from_storage_utc, to_storage_utc


def content_hash(job: JobPosting) -> str:
    """Hash the parts of a posting that determine whether it "changed".

    Deliberately excludes `fetched_at`/`last_seen_at`/`expires_at`/`active` so a
    re-import that only refreshes freshness timestamps is detected as unchanged.
    """
    payload = {
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "summary": job.summary,
        "requirements": [r.model_dump(mode="json") for r in job.requirements],
        "other_requirements": job.other_requirements,
        "evidence": [e.model_dump(mode="json") for e in job.evidence],
        "language": job.language,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def job_version_fields(job: JobPosting) -> dict:
    """Column values for a `JobVersionRow` built from a `JobPosting`."""
    return {
        "job_id": job.job_id,
        "content_version": job.content_version,
        "source_id": job.source_id,
        "source_url": str(job.source_url),
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "summary": job.summary,
        "requirements": [r.model_dump(mode="json") for r in job.requirements],
        "other_requirements": list(job.other_requirements),
        "evidence": [e.model_dump(mode="json") for e in job.evidence],
        "language": job.language,
        "fetched_at": to_storage_utc(job.fetched_at),
        "last_seen_at": to_storage_utc(job.last_seen_at),
        "posted_at": job.posted_at and to_storage_utc(job.posted_at),
        "expires_at": job.expires_at and to_storage_utc(job.expires_at),
        "active": job.active,
        "data_origin": job.data_origin,
        "content_hash": content_hash(job),
    }


def version_row_to_posting(row) -> JobPosting:
    return JobPosting.model_validate(
        {
            "job_id": row.job_id,
            "source_id": row.source_id,
            "source_url": row.source_url,
            "content_version": row.content_version,
            "title": row.title,
            "company": row.company,
            "description": row.description,
            "summary": row.summary,
            "requirements": row.requirements,
            "other_requirements": row.other_requirements,
            "evidence": row.evidence,
            "language": row.language,
            "fetched_at": from_storage_utc(row.fetched_at),
            "last_seen_at": from_storage_utc(row.last_seen_at),
            "posted_at": from_storage_utc(row.posted_at),
            "expires_at": from_storage_utc(row.expires_at),
            "active": row.active,
            "data_origin": row.data_origin,
        }
    )


def event_row_fields(event: JobChangeEvent, *, created_at: datetime) -> dict:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "job_id": event.job_id,
        "job_version": event.job_version,
        "occurred_at": to_storage_utc(event.occurred_at),
        "content_ref": event.content_ref,
        "created_at": to_storage_utc(created_at),
    }


def event_row_to_event(row) -> JobChangeEvent:
    return JobChangeEvent.model_validate(
        {
            "event_id": row.event_id,
            "event_type": row.event_type,
            "job_id": row.job_id,
            "job_version": row.job_version,
            "occurred_at": from_storage_utc(row.occurred_at),
            "content_ref": row.content_ref,
        }
    )
