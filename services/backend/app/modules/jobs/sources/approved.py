"""The approved job sources. Owner: M2 (B-01).

The single place a host becomes importable. Each entry needs recorded
robots.txt/ToS evidence in docs/job-sources/REGISTER.md first; the ingestion
service rejects every host not listed here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovedSource:
    source_id: str
    name: str
    host: str
    example_url: str
    approved_on: str

    @property
    def base_url(self) -> str:
        return f"https://{self.host}"


APPROVED_SOURCES: tuple[ApprovedSource, ...] = (
    ApprovedSource(
        "greenhouse",
        "Greenhouse",
        "job-boards.greenhouse.io",
        "https://job-boards.greenhouse.io/<company>/jobs/<id>",
        "2026-09-15",
    ),
    ApprovedSource(
        "lever",
        "Lever",
        "jobs.lever.co",
        "https://jobs.lever.co/<company>/<posting-id>",
        "2026-09-19",
    ),
    ApprovedSource(
        "ashby",
        "Ashby",
        "jobs.ashbyhq.com",
        "https://jobs.ashbyhq.com/<company>/<posting-id>",
        "2026-09-19",
    ),
)

APPROVED_HOSTS = frozenset(source.host for source in APPROVED_SOURCES)
SOURCE_IDS_BY_HOST = {source.host: source.source_id for source in APPROVED_SOURCES}


def register_approved_sources(repository) -> None:
    """Idempotently record every approved source in `job_sources`."""
    for source in APPROVED_SOURCES:
        repository.register(
            source.source_id,
            source.name,
            source.base_url,
            "ats",
            True,
            permitted_notes=(f"Approved {source.approved_on}; see docs/job-sources/REGISTER.md."),
        )
