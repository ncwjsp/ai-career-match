"""The approved-source list (B-01) that every import entry point shares."""

from app.modules.jobs.sources.approved import (
    APPROVED_HOSTS,
    APPROVED_SOURCES,
    SOURCE_IDS_BY_HOST,
)


def test_hosts_and_source_ids_are_unique():
    assert len({s.host for s in APPROVED_SOURCES}) == len(APPROVED_SOURCES)
    assert len({s.source_id for s in APPROVED_SOURCES}) == len(APPROVED_SOURCES)


def test_the_approved_hosts_are_exactly_the_registered_ones():
    assert APPROVED_HOSTS == {"job-boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com"}
    assert SOURCE_IDS_BY_HOST["jobs.lever.co"] == "lever"
    assert SOURCE_IDS_BY_HOST["jobs.ashbyhq.com"] == "ashby"
