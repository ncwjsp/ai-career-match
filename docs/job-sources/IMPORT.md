# Manual URL import (B-02)

Owner: M2. Implements R04's "manually import an individual permitted job URL;
re-import a URL to update its posting" against the one approved source
(`docs/job-sources/REGISTER.md`).

## What exists

`app/modules/jobs/ingest.py`'s `JobIngestionService`:

- `import_url(url)` -- rejects a non-HTTPS URL or a host outside the approved
  allow-list immediately (`UnsupportedSourceError`, no import-run record
  created: this is a request validation error, not an attempt). Otherwise
  fetches via B-01's `fetch_single_posting`, records the raw response
  (`job_raw_snapshots`), normalizes it (`normalize.py`), and compares its
  content hash (`app.db.jobs.mapping.content_hash`) against the job's current
  stored version:
  - No existing job for this URL -> a new `job_versions` row (version 1),
    `jobs` row, and `job.created` event, committed atomically via
    `JobRepository.save_with_event`. Import run status `success`.
  - An existing job, content changed -> a new version, `job.updated` event.
    Import run status `success`.
  - An existing job, content unchanged -> **no** new version and **no**
    event. Import run status `unchanged`. This is what "unchanged re-import
    emits no duplicate event" means in practice: the check is recorded (via
    `job_import_runs`, so freshness/"last checked" is still visible), but
    nothing is written to `jobs`/`job_versions`/`job_change_events`.
  - The fetch itself fails -> import run status `failed` with the error
    message; `jobs`/`job_versions`/`job_change_events` are never touched, so
    prior data survives a failed check untouched.
- `mark_closed(job_id)` -- the manual "no longer available" action: a new
  version with `active=False` and a `job.expired` event. A no-op (returns the
  existing posting unchanged, no new version) if the job is unknown or
  already closed.

`app/modules/jobs/normalize.py` turns fetched HTML into `JobPosting` fields.
It prefers a schema.org `JobPosting` block in an `application/ld+json` tag
when the host embeds one (structured title/company/description/dates, no
guessing); otherwise it falls back to the page's `<title>` tag and full
visible text. Required/preferred skills come from the same alias-based
`app.nlp.skills.find_skills` matcher A-02/B-04/B-06 already share, applied
directly (not through `SharedTextProcessor`'s spaCy-dependent `analyze()`,
which this does not need and which is not an installed dependency here).

`app/modules/jobs/html_text.py` is the stdlib-only HTML/JSON-LD extraction
`normalize.py` is built on -- no BeautifulSoup/lxml, so no new runtime
dependency to coordinate with M3.

`app/modules/jobs/summary.py` is a deterministic extractive summary
(leading sentences up to a character budget) for `JobPosting.summary` --
not an LLM call; that is a different, M3-owned R10 producer (C-02).

URLs are canonicalized (scheme + lowercased host + path, query/fragment
dropped) before deriving a job's identity, so `.../jobs/123` and
`.../jobs/123?ref=email` resolve to the same job and a re-import via either
form is detected correctly as new/changed/unchanged against the same job.

All of the above is tested against the real Alembic-migrated `career_jobs`
schema with a fake HTTP transport (`tests/jobs/test_ingest.py`,
`test_normalize.py`, `test_html_text.py`, `test_summary.py`) -- no real
network, no new dependency.

## What is deliberately not built yet: the router

`docs/integration/OWNERSHIP.md` and plan.md section 3 both say the import
request/status wire contract -- `JobImportRequest`/`JobImportRun` response
DTOs, and the team-only access guard D09 asks for -- is a small M3 follow-up
PR to agree before integration. The existing `JobIngestor.run(source_id)`
port in `app.contracts.interfaces` predates B-01 and was never meant to
describe this URL-based flow either (plan.md: "The current
`JobIngestor.run(source_id)` port is not yet this URL API").

Building `POST /api/v1/job-imports` / `GET /api/v1/job-imports/{id}` /
`PATCH /api/v1/jobs/{id}` now, with invented DTOs, would risk a second,
competing shape for exactly the objects plan.md says M3 owns. `import_url`
and `mark_closed` above are the domain operations a future router calls once
that contract is agreed; nothing about them should need to change when it
is -- only a thin router layer gets added on top.
