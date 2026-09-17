# A-05 / A-06: intake and profile experience

Owner: Plai (M1). Uses M3's session/storage/queue/repositories and M2's existing matcher.

## Implemented flow

1. `POST /api/v1/resumes` accepts one English PDF/DOCX, verifies type/size and returns
   `UploadAccepted` with HTTP 202. A request-level multipart limit protects temporary
   storage; file bytes are limited separately. Parsing happens in the worker.
2. Reuse the retained anonymous session or create one. An HttpOnly, SameSite=Lax cookie
   scopes reads; production adds Secure. Original filenames are not retained.
3. Store bytes through local/S3 `ObjectStore`. Lock the candidate row and commit upload
   metadata, analysis state and queue payload together in `career_app`. A second inflight
   upload for that candidate returns 409. Failed DB intake compensates the stored object.
4. Worker validates/extracts with A-01, analyzes with A-02 local/SageMaker NLP, constructs
   A-03 facts and evidence, persists profile and A-04 candidate embedding, and queues a
   stable `profile.ready` event. Unknown/negated/uncertain facts retain A-03 behavior.
5. M2/M3 matching publishes recommendations independently. The worker reconciles analysis
   to `ready`, including an empty corpus. Later job imports match retained candidates
   through the existing job event path, without uploading or parsing the resume again.
6. `GET /api/v1/analyses/{id}` and `/resumes/{id}/profile` require the owning session and
   return no-store responses. A foreign/unknown resource is not disclosed. Files are not
   exposed as public URLs.

Resume retries reuse the persisted profile and stable event ID. Present-date experience
uses the analysis creation date so restart does not change facts. Lease heartbeat and
owner-checked acknowledge/retry prevent an old claimant completing a replacement's job.
Irrecoverable extraction/NLP failures are terminal and safe to show; dependency errors
use bounded retries and a parked failure becomes visible to the browser. Review production
concurrency on PostgreSQL before adding worker replicas; SQLite tests do not prove row locks.

The frontend exports `ResumeUpload`, `AnalysisProgress` and `ProfileView`. The home page
mounts upload; `/analysis/{id}?resume=...&candidate=...` can be reloaded in the same session.
It shows real stages, actionable errors, profile facts, unknowns, warnings and evidence,
then links to M3's recommendations page. No invented percentage progress or scores.
The file remains selected after upload failure so the user can retry. Only opaque IDs
appear in the reload link; it confers no access without the cookie.

## Running the full local flow

Start both PostgreSQL databases and apply both independent migration chains using README.
Install/package the CPU model using [A-04/A-07](A04_A07_MODELS.md). From `services/backend`,
run these in separate terminals after setting `EMBEDDING_BACKEND=cpu`:

```bash
uv run --extra ml uvicorn app.main:app --host 127.0.0.1 --port 8000
uv run --extra ml python -m scripts.run_worker
```

From `apps/web`: `pnpm dev`. Upload a synthetic English resume with explicit section
headings such as Skills, Experience and Education. The UI accepts 10 MB; if deployment
lowers the backend limit, its structured error remains authoritative. A profile with
no supported matchable facts is rejected rather than embedding invented content.

## Verification

- `uv run pytest tests/resume tests/nlp tests/app/test_queue.py`
- `pnpm test:resume` (first install Chromium: `pnpm exec playwright install chromium`)
- `pnpm lint`, `pnpm typecheck`, `pnpm build`, `pnpm api:check`

API tests use real parsers/NLP, migrated SQLite application tables, local storage and
synthetic vectors. Browser tests intercept API requests using canonical synthetic fixtures;
they verify upload/progress/profile/reload/error/retry/accessibility labels, not a deployed
system. The real model parity test is separately opt-in. No real resume or live source is
used in these tests.

## Shared changes for Nai review

No canonical public DTO or migration changed. Required shared edits: promoted A-02 pins
and optional CPU ML dependencies; `cpu` adapter setting; mounted resume and existing M2
read routers; OpenAPI/generated types; worker composition; optional queue owner/renewal
methods; empty-corpus profile-version publication; frontend client/routes/config and tests.
M2 behavior is untouched; three pre-existing M2 formatting failures were formatted only.

Use a single worker instance for the first deployment. Confirm PostgreSQL concurrency,
retention cleanup, backup/recovery and S3 orphan handling with M3 before scale-out. An
object-store write and SQL commit cannot be one cross-service transaction: a process crash
between them can leave an orphan object; configure an operational orphan sweep/lifecycle
without deleting objects referenced by uploads. Live AWS and hosting remain deployment gates.
