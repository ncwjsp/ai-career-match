# Resume PostgreSQL validation

PR #14 merged as `fae9b09` on 2026-09-18. This follow-up checks the A-05
intake and analysis queue using PostgreSQL 17.11, not SQLite.

## Run

Use a disposable PostgreSQL database. Its role needs permission to create schemas.
From `services/backend`, set `ACM_TEST_POSTGRES_URL` to its SQLAlchemy psycopg URL:

```powershell
$env:ACM_TEST_POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:PORT/TEST_DATABASE'
uv run pytest tests/resume/test_api_worker.py tests/resume/test_postgres_concurrency.py
```

Each test creates a unique `resume_test_<uuid>` schema, runs the real application
migrations inside it, and drops only that schema afterwards. No existing tables
are truncated. The connection uses a 15-second statement timeout so a lock
regression fails instead of hanging indefinitely. Without the variable, the
existing SQLite tests still run and the three PostgreSQL-only tests skip.

## Coverage and evidence

- Two concurrent uploads for the same candidate: exactly one accepted, one
  conflict, one metadata/analysis/queue record and one retained local object.
- Eight concurrent queue claimants: distinct work items, skipping a row held
  locked by another transaction, then claiming that row after its lock releases.
- Expired lease reclamation: the previous owner cannot renew, acknowledge or
  retry the new owner's work.
- The existing 12 intake/worker tests also run on PostgreSQL, including session
  isolation, rollback, upload-to-ready and new-job refresh without re-extraction.

Local result on 2026-09-18: **15 passed**, two upstream deprecation warnings.
CI's database job now runs this same suite after role/isolation/migration checks.
CI results for this follow-up must be checked separately after publication.

The fixture follows `tests/conftest.py`'s migration-per-test convention and
`tests/resume/test_api_worker.py`'s container/adapters. Production code, DTOs,
dependencies and migrations are unchanged. M3 owns review of the CI addition.

This is bounded PostgreSQL concurrency evidence, not a production load test.
Jobs and embeddings in the flow tests remain synthetic adapters. Live S3,
SageMaker, both-database end-to-end validation, crash testing of complete worker
processes and deployment sizing remain open. M2 retrieval/research is unchanged.
