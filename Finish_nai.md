# Finish — Nai (M3): integration, results, explanations, deployment

Branch: `feat/m3/nai-integration`, from `main` at `b09b4f5`.
Date: 2026-09-08. Owner: Nai (M3).

Read this before continuing my part or building on it. It says what exists, what
was actually measured, what is deliberately not done, and exactly how M1 and M2
plug into it.

---

## 1. Scope change I applied first

The team moved back to **AWS S3** (resume originals) and **Amazon SageMaker**
(NLP/embedding inference). I updated `plan.md`, `START_HERE.md`, `README.md` and
`docs/integration/OWNERSHIP.md` for that, and recorded every required variable
in `services/backend/.env.example`.

What did **not** change: the two-database split, manual URL imports, both
matching triggers, the 70/30 scoring formula, the research scope, and the
ownership map. **OpenSearch and Bedrock stay out of the MVP** — retrieval is
still stored vectors plus exact cosine (B-03), and Bedrock is only now an
*allowed* provider behind the neutral LLM adapter.

Still undecided (D07): where web/API/worker/PostgreSQL actually run. Railway is
still viable; an AWS-native host is now also possible. Cross-provider egress and
latency have to be measured before that is frozen.

**No AWS key is needed to run or test this checkout.** Every cloud adapter has a
local counterpart and the defaults select it.

---

## 2. What I built

### C-01 — application persistence, storage, inference, durable queue
- `app/core/settings.py` — one configuration for both processes.
  `validate_for_runtime()` replaces the old blanket "production is unsupported"
  guard: production must declare `APP_MODE=real`, and a named cloud backend must
  carry the bucket or endpoint it needs. A misconfigured deployment fails at
  startup instead of quietly serving mocks.
- `app/core/errors.py`, `clock.py`, `ids.py`, `timeutil.py` — error taxonomy the
  API turns into the canonical `ErrorResponse`, injectable time (retention and
  leases are testable), opaque identifiers, UTC normalization.
- `app/core/storage.py` — `LocalObjectStore` (tests/CI/offline) and
  `S3ObjectStore` (deployment). Keys are generated and opaque; there is **no
  presigned or public URL**, so every read stays authorized by the application.
  A missing object is `NotFound`; a failing bucket is a retryable
  `DependencyUnavailable`, never an empty resume.
- `app/core/inference.py` — the SageMaker transport plus a deterministic offline
  client. Every response is checked against its declared dimensions, model id
  and revision; a short, zero or non-finite vector is an outage, not a stored
  value. **The endpoint's JSON contract is in that module's docstring — M1's
  A-07 packaging must serve it.**
- `app/db/app/` — the `career_app` schema (13 tables), its migration chain,
  sessions, profiles, uploads, embeddings, analyses, matches, revisions,
  explanations and the durable queue.
- `migrations/app/versions/0001_app_schema.py` — independent of M2's chain.

### C-08 — job-change dispatch and incremental matching
- `app/orchestration/job_events.py` — `OutboxDispatcher` inserts into the
  `career_app` queue **first** and acknowledges `career_jobs` second, so a crash
  redelivers rather than loses; the queue's `event_id` primary key absorbs the
  duplicate. `MatchService` handles `profile.ready`, `job.created/updated`,
  `job.expired/removed` and `reconciliation.requested`.
- `app/orchestration/refresh.py` — publishes one coherent revision per
  candidate, excludes inactive/expired/superseded postings even before their
  cleanup event is consumed, and returns early when nothing changed.
- `app/orchestration/worker.py`, `runs.py`, `retention.py`,
  `scripts/run_worker.py`.

### C-02 — grounded explanations
`app/modules/explanations/` — evidence context, fenced untrusted document text,
the prompt and its version, a provider-neutral client (Bedrock + offline), and
validation of every reply against the computed score, strengths and gaps.
Failure produces the `unavailable` state with the real evidence still shown.

### C-03 / C-04 — frontend
Typed client, polling hook, shared states, ranked list, skill breakdown, job
detail and explanation panel; routes under `/recommendations/[candidateId]`.

### C-05 / C-06 / C-07
Composition root and access rules (`app/core/container.py`, `access.py`),
explanation routes, container images, `docs/integration/DEPLOYMENT.md`,
regenerated contracts, and the tracker updates.

Plus one thing that was blocking everyone: **A-01's `pypdf` / `defusedxml` were
only in a temporary handoff file**, so `uv sync --locked` could not run
`tests/resume` on a fresh clone. They are now in `pyproject.toml` and `uv.lock`.

---

## 3. What I actually ran (2026-09-08, macOS, Python 3.12.14)

| Check | Result |
| --- | --- |
| `pytest` (backend) | **257 passed**, 2 pre-existing upstream deprecation warnings |
| `ruff check .` / `ruff format --check .` | pass |
| `scripts.export_openapi --check` | snapshot current |
| `next build`, `tsc --noEmit`, `eslint .`, `api-types --check` | pass |

Test counts by area: 43 `tests/core` (settings, storage, inference, access,
worker entry, health, migrations), 56 `tests/app` (schema, sessions, profiles,
matches, analyses, queue), 32 `tests/integration` (C-08 refresh flow and the
explanation API), 21 `tests/explanations`, plus the existing 20 contracts,
27 jobs and 58 resume tests, which still pass.

**Honest limits on that evidence:**
- Tests run against **SQLite**, not PostgreSQL — no Docker daemon here. The
  schema is dialect-portable and CI's `databases` job covers the real path, but
  I have not seen it pass. `FOR UPDATE SKIP LOCKED` in particular is exercised
  only on PostgreSQL.
- The frontend was verified with `npm`-installed dependencies and Node 22,
  because pnpm and Node 24 are not on this machine. **Please rerun
  `pnpm install --frozen-lockfile && pnpm lint typecheck build` on a proper
  setup before merging.**
- **No GitHub CI run and no teammate review is recorded.**
- No AWS call was ever made. Every S3, SageMaker and Bedrock test injects a fake
  client.
- The S3, SageMaker and Bedrock adapters are **unproven against the real
  services**. They are written to the documented APIs and nothing more.

---

## 4. What is deliberately not done

- **Resume upload API and profile read** (`POST /api/v1/resumes`,
  `/resumes/{id}/profile`) — A-05, M1's. Still 501.
- **Jobs and recommendations reads** (`/api/v1/jobs/{id}`,
  `/candidates/{id}/recommendations`) — B-06, M2's. Still 501. The result UI
  therefore shows a documented "not available yet" state, not a fake list.
- **Real scoring** — B-04/B-06/B-10. `scripts/run_worker.py` refuses to start
  without M2's matcher instead of publishing fixture scores.
- **The manual import route** — M2's component and importer. I built only the
  server-side guard (`require_import_access`, D09).
- **Anything provisioned.** No AWS account, bucket, endpoint, host, budget or
  deployment. INT-02 cannot be claimed from this branch.
- **D06 durations.** `PROFILE_RETENTION_DAYS=30` is a placeholder, not a policy.

---

## 5. How to plug into my code

### M1 (Plai) — A-04, A-05
```python
from app.core.container import Container
from app.core.settings import Settings

container = Container(settings=Settings())

session_id, candidate_id = container.sessions.start()   # one anonymous session
file = container.object_store.put(upload_bytes, "application/pdf")
container.uploads.record(resume_id, candidate_id, file, len(upload_bytes))
run = container.analyses.create(analysis_id, candidate_id, resume_id)
container.analysis_queue.enqueue(run, file)             # the worker takes it
```
Set the session cookie with `app.core.access.set_session_cookie`; every
candidate-scoped read goes through `candidate_scope`.

After the profile exists: `container.profiles.save(profile)` then enqueue a
`ProfileReadyEvent` on `container.match_queue`. `save` refuses to rewrite a
stored version, so give a re-parse a new `profile_version`.

For A-04/A-07: wrap `container.embedding_client` (an `EmbeddingClient`) in your
`Embedder`. The endpoint contract is in `app/core/inference.py`; parity is now
**local versus SageMaker**.

### M2 (Baibua) — B-02, B-06, B-10
- Keep committing the job version and its outbox event in one `career_jobs`
  transaction, as B-09 already does. My dispatcher does the rest; you do not
  need to call anything in `career_app`.
- Your matcher must satisfy `app.contracts.interfaces.Matcher` and live at
  `app.modules.matching.scoring.Matcher` for `scripts/run_worker.py` to find it.
  `score_pair` and `match_job` must give the **same** score for a pair —
  `tests/integration/test_incremental_matching.py` asserts this with a fake.
- Guard your import route with
  `Depends(app.core.access.require_import_access)`, and tell me the request /
  status DTOs you need so I can add them to the contracts.
- `tests/integration/fakes.py::CountingMatcher` shows the shape my tests expect.

### Next person on M3
Highest value first:
1. Run the suite against real PostgreSQL (`infra/compose.yaml`) and confirm the
   claim-under-concurrency path.
2. Mount A-06's upload feature and M2's import component in `src/app/`.
3. Settle D06 durations and D07 host/budget; only then provision anything.
4. INT-01 with real A-05 + B-06, then INT-02.

---

## 6. Environment

Everything needed is named in `services/backend/.env.example`:
`OBJECT_STORE_BACKEND` / `RESUME_BUCKET` / `RESUME_OBJECT_PREFIX` / `AWS_REGION`
(and `AWS_S3_ENDPOINT_URL` for a MinIO dry run), `EMBEDDING_BACKEND` /
`SAGEMAKER_EMBEDDING_ENDPOINT` / `SAGEMAKER_REGION` /
`SAGEMAKER_TIMEOUT_SECONDS`, `LLM_PROVIDER` / `LLM_MODEL_ID` / `LLM_API_KEY`,
`PROFILE_RETENTION_DAYS` / `MATCH_BATCH_SIZE` / `MAX_UPLOAD_BYTES`, and
`IMPORT_ACCESS_TOKENS`.

Credentials come from an instance/task role, `AWS_PROFILE`, or the standard
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` that boto3
reads by itself. **No key is committed, and none belongs in a `NEXT_PUBLIC_`
variable.** The IAM policy to scope them is in
`docs/integration/DEPLOYMENT.md`.
