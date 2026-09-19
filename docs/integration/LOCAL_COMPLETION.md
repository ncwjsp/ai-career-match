# Local application completion — 2026-09-19

Plai authorized completing the remaining M2/M3 implementation without waiting
for teammates. AWS deployment is deferred because the account/host/budget are
not ready. Existing ownership labels describe module responsibility, not a blocker.

## Try the application

Follow README for PostgreSQL migrations, CPU model packaging and the three
API/worker/web processes. Keep `uv run --extra ml` on API/worker commands.

Set a private team token in `services/backend/.env`:

```dotenv
IMPORT_ACCESS_TOKENS=replace-with-your-local-team-token
```

Restart the API after editing the environment. Open `/job-import` from the
home page's **Team: add or update jobs** link. Enter the same token and a direct
`https://job-boards.greenhouse.io/<company>/jobs/<id>` posting URL. The token
stays in page memory, is sent only in the Authorization header, and is not
saved in browser storage. Do not put it in a NEXT_PUBLIC variable.

Successful imports persist in `career_jobs`. Re-importing unchanged content
does not emit a new event; changed postings refresh retained candidates via
the worker. Existing data survives fetch failures. Redirects, URL credentials
and custom ports are rejected. Only the existing approved host is supported.

The API currently completes one bounded import synchronously and returns the
canonical IngestionReport. A timeout should be retried with the same URL;
content/version deduplication handles an already completed import. There is
no scheduler, crawler or background import queue.

## What changed

- New canonical JobImportRequest and guarded POST `/api/v1/job-imports`;
  existing IngestionReport reused; OpenAPI and frontend types regenerated.
- `/job-import` form, success/unchanged/failure feedback and home navigation.
- Worker reuses versioned candidate/job vectors from their respective
  databases. Missing vectors are computed and stored; incompatible model
  metadata fails rather than blending vector spaces. Both triggers keep the
  same 70/30 formula and exact scoring across the active corpus.
- Two-database integration test uses the real import service, repositories,
  outbox, resume processing and matcher; source HTTP and embedding responses
  are synthetic. PostgreSQL opt-in uses distinct disposable databases and
  per-test schemas. CI now runs this flow too.
- Optional cross-encoder, LDA and a five-method research CLI. See
  [research completion](../../research/evaluation/COMPLETION.md).

## Limits that remain

No AWS resources were created. S3/SageMaker remain required for deployment.
Real provider calls, deployment/retention decisions, backup/restore and
complete multi-process crash/load acceptance still require staging.

Human relevance labels and a representative permitted job corpus have not
been supplied. Research smoke results establish executability, not matching
quality. No synthetic label is presented as a human judgment. The live app
keeps the 70/30 baseline until evaluation supports a model/formula change.

Use one worker for the current local setup. Concurrency tests for queue claims
are not evidence that the entire distributed pipeline supports replicas.
The legacy on-demand Matcher.recommend interface remains unused: the live
API reads coherent published recommendations from the event-driven pipeline.
