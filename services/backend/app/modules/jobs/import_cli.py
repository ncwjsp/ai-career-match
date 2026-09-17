"""One-command real job import. Owner: M2 (B-02/B-07 corpus-building tool).

This sandboxed session's network egress to job/career sites is blocked by
organization policy (confirmed the same way as B-01, see
docs/job-sources/REGISTER.md) -- so a real import cannot be run here. Run
this from a machine with normal network access to actually persist one
approved posting into `career_jobs`, which is exactly the real,
non-fixture data B-07's LDA topic modeling needs and does not yet have.

    cd services/backend
    JOB_DATABASE_URL=sqlite:///career_jobs.sqlite \
        uv run alembic -c alembic-jobs.ini upgrade head
    JOB_DATABASE_URL=sqlite:///career_jobs.sqlite \
        uv run python -m app.modules.jobs.import_cli \
        https://job-boards.greenhouse.io/<company>/jobs/<id>

`JOB_DATABASE_URL` can instead point at a real PostgreSQL `career_jobs`
database (the default in `app.core.settings.Settings`) once one exists;
nothing here is SQLite-specific. Re-running the same URL later is safe and
is in fact how B-02's "explicit re-import" is meant to be used -- unchanged
content produces no duplicate event, changed content bumps the version.

Registers "greenhouse" as a `job_sources` row on first use (idempotent: a
second registration just updates the same row), then runs
`JobIngestionService.import_url()` against the real network via the default
`UrllibTransport` and prints the resulting `IngestionReport`.

Only `job-boards.greenhouse.io` is in the allow-list here because it is the
only source docs/job-sources/REGISTER.md records as approved. Adding another
host requires the same live robots.txt/ToS verification B-01 did for this
one -- this script deliberately does not let a caller pass an arbitrary host.
"""

from __future__ import annotations

import argparse
import sys

from app.core.clock import SystemClock
from app.core.settings import Settings
from app.db.jobs.database import create_job_engine, session_factory
from app.db.jobs.repository import SqlJobRepository
from app.db.jobs.sources import (
    SqlJobImportRunRepository,
    SqlJobRawSnapshotRepository,
    SqlJobSourceRepository,
)
from app.modules.jobs.ingest import JobIngestionService, UnsupportedSourceError

APPROVED_HOSTS = frozenset({"job-boards.greenhouse.io"})
SOURCE_ID = "greenhouse"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "url",
        help="An approved posting URL, e.g. https://job-boards.greenhouse.io/<company>/jobs/<id>",
    )
    args = parser.parse_args(argv)

    factory = session_factory(create_job_engine(Settings()))
    jobs = SqlJobRepository(factory)
    import_runs = SqlJobImportRunRepository(factory)
    raw_snapshots = SqlJobRawSnapshotRepository(factory)
    sources = SqlJobSourceRepository(factory)

    sources.register(
        SOURCE_ID,
        "Greenhouse",
        "https://job-boards.greenhouse.io",
        "ats",
        True,
        permitted_notes="Approved 2026-09-15; see docs/job-sources/REGISTER.md.",
    )

    service = JobIngestionService(
        jobs,
        import_runs,
        raw_snapshots,
        allowed_hosts=APPROVED_HOSTS,
        source_id=SOURCE_ID,
        clock=SystemClock(),
    )

    try:
        report = service.import_url(args.url)
    except UnsupportedSourceError as error:
        print(f"Rejected: {error}", file=sys.stderr)
        return 2

    print(f"run_id={report.run_id}")
    print(
        f"new_jobs={report.new_jobs} changed_jobs={report.changed_jobs} "
        f"unchanged_jobs={report.unchanged_jobs}"
    )
    if report.warnings:
        print(f"FAILED: {report.warnings}", file=sys.stderr)
        return 1
    if report.new_jobs or report.changed_jobs:
        print("Imported successfully -- one real job now stored in career_jobs.")
    else:
        print("No change since the last import of this URL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
