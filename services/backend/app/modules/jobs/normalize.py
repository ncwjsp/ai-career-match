"""Turn a fetched posting's raw HTML into `JobPosting`-ready fields. Owner: M2 (B-02).

Two sources of structured data, tried in order:

  1. A schema.org `JobPosting` block in an `application/ld+json` tag, when the
     host embeds one -- common for ATS-hosted boards, including Greenhouse.
     Gives a real title/company/description/dates instead of a guess.
  2. Fallback: the page's `<title>` tag (split on a separator like " at ") and
     its full visible text, when no JobPosting JSON-LD is present.

Required/preferred skills come from `app.nlp.skills.find_skills` -- the same
alias-based, regex-only matcher A-02/B-04/B-06 already share for resumes and
job text, applied here to the normalized description with a single
whole-document evidence span. This deliberately does NOT go through
`app.nlp.processor.SharedTextProcessor`, whose `analyze()` also runs a spaCy
pipeline for tokens/entities this module does not need and spaCy is not an
installed dependency in this environment; `find_skills` itself needs only the
standard library.

`document_id` should be the caller's stable job identifier (not a per-fetch
snapshot id) -- content_hash-based change detection in `ingest.py` depends on
evidence being identical across re-imports of unchanged content, so evidence
identity must not vary run to run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.contracts.models import EvidenceRef, JobRequirement, ProcessedText
from app.modules.jobs.html_text import (
    extract_json_ld_jobposting,
    extract_title_tag,
    extract_visible_text,
)
from app.nlp.skills import find_skills
from app.nlp.text import normalize_text

_TITLE_SPLIT = re.compile(r"\s+(?:at|@|\|| - )\s+", re.IGNORECASE)
_ASSERTION_RANK = {"mentioned": 2, "uncertain": 1}


@dataclass(frozen=True)
class NormalizedPosting:
    title: str
    company: str
    description: str
    requirements: list[JobRequirement]
    other_requirements: list[str]
    evidence: list[EvidenceRef]
    language: str | None
    posted_at: datetime | None
    expires_at: datetime | None


def _strip_html_fragment(value: str) -> str:
    if "<" in value and ">" in value:
        return extract_visible_text(value)
    return value.strip()


def _guess_title_company(html: str) -> tuple[str, str]:
    raw_title = extract_title_tag(html) or "Untitled posting"
    parts = _TITLE_SPLIT.split(raw_title, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return raw_title.strip(), "Unknown"


def _parse_datetime(value: object) -> datetime | None:
    """schema.org `datePosted`/`validThrough` are often a bare date (no time or
    offset) -- treat a naive result as UTC so it satisfies `JobPosting`'s
    `AwareDatetime` fields instead of failing validation."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _extract_requirements(description: str, evidence_ref: EvidenceRef) -> list[JobRequirement]:
    source = ProcessedText(
        text=description,
        language="en",
        preprocessing_version="raw-text-v1",
        evidence=[evidence_ref],
    )
    normalized = normalize_text(description)
    mentions = find_skills(source, normalized)

    best_state: dict[str, str] = {}
    best_evidence: dict[str, list[EvidenceRef]] = {}
    for mention in mentions:
        if mention.assertion == "negated":
            continue
        rank = _ASSERTION_RANK[mention.assertion]
        current = best_state.get(mention.canonical)
        if current is None or rank > _ASSERTION_RANK[current]:
            best_state[mention.canonical] = mention.assertion
            best_evidence[mention.canonical] = list(mention.evidence)
        elif rank == _ASSERTION_RANK[current]:
            best_evidence[mention.canonical].extend(mention.evidence)

    return [
        JobRequirement(
            skill=skill,
            required=(state == "mentioned"),
            evidence=best_evidence[skill],
        )
        for skill, state in sorted(best_state.items())
    ]


def normalize_posting(html: str, *, document_id: str, fetched_at: datetime) -> NormalizedPosting:
    job_ld = extract_json_ld_jobposting(html)
    if job_ld is not None:
        title = str(job_ld.get("title") or "").strip() or "Untitled posting"
        org = job_ld.get("hiringOrganization")
        if isinstance(org, dict) and org.get("name"):
            company = str(org["name"]).strip()
        elif isinstance(org, str) and org.strip():
            company = org.strip()
        else:
            company = "Unknown"
        raw_description = _strip_html_fragment(str(job_ld.get("description") or ""))
        description = raw_description or extract_visible_text(html)
        posted_at = _parse_datetime(job_ld.get("datePosted"))
        expires_at = _parse_datetime(job_ld.get("validThrough"))
    else:
        title, company = _guess_title_company(html)
        description = extract_visible_text(html)
        posted_at = None
        expires_at = None

    if not description.strip():
        description = "(no description text was found on this posting)"

    document_evidence = EvidenceRef(
        document_id=document_id,
        document_version=1,
        chunk_id="description-0001",
        start=0,
        end=len(description),
        excerpt=description,
    )
    requirements = _extract_requirements(description, document_evidence)

    return NormalizedPosting(
        title=title,
        company=company,
        description=description,
        requirements=requirements,
        other_requirements=[],
        evidence=[document_evidence],
        language="en",
        posted_at=posted_at,
        expires_at=expires_at,
    )
