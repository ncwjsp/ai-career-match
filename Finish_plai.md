# Plai (M1) completion handoff

Branch: `feat/m1/complete-resume-pipeline`, based on main `c086974`.
Date: 2026-09-17. Review/merge is still required; do not treat this as production approval.

## What is implemented

| Task | Delivery | Remaining acceptance gate |
| --- | --- | --- |
| A-01 / A-02 / A-03 | Previously merged extraction, English NLP and evidence-backed profiles | Regressions retained; no rewrite |
| A-04 | Versioned 384-dimensional embeddings, reviewed model hashes, token chunking, batch encoding, CPU/SageMaker compatibility checks | M2 validates selected model on labeled data |
| A-05 | Bounded PDF/DOCX upload; session isolation; atomic upload metadata/analysis queue; profile/analysis reads; parsing/NLP/profile/vector/event worker; retry/recovery | Review PostgreSQL concurrency and live S3 |
| A-06 | Upload, processing/error/retry states, factual profile/evidence and reloadable analysis page; results link | Teammate review and deployed acceptance |
| A-07 | Offline CPU artifact build, optional locked ML runtime, SageMaker-compatible container and NLP/embedding protocol, parity tests and measurement script | Live endpoint/instance measurements, IAM and approved deployment |

Local runtime: [A-05/A-06 guide](docs/resume/A05_A06_INTAKE.md).
Model version, packaging, endpoint protocol and measured limits:
[A-04/A-07 guide](docs/resume/A04_A07_MODELS.md).

## Patterns followed and shared review

| Concern | Existing precedent | Adaptation |
| --- | --- | --- |
| HTTP/errors/session | `app/modules/explanations/router.py`, `app/core/access.py` | Same container, structured errors and session access; private reads are no-store |
| Persistence/queue | `app/db/app/profiles.py`, `analyses.py`, `queue.py` | Reuse M3 tables; intake writes its metadata and work in one SQL transaction; no migration |
| Events/recovery | `app/orchestration/worker.py`, `job_events.py` | Stable profile-ready event feeds existing matching; analysis reconciles published results |
| Embedding transport | `app/core/inference.py` | Preserve existing JSON protocol, add pinned CPU implementation and version gate |
| Frontend/errors | `RecommendationList.tsx`, `usePolling.ts`, `states.tsx` | Same API client and polling/error components; resume feature owns its UI |

Shared edits for **Nai / M3**: backend dependency manifest/lock, optional ML dependencies,
CPU setting/factory, queue lease owner/renewal, worker composition, mounted existing M2
read APIs, OpenAPI/types, empty-corpus profile-version publication, web routes/client,
proxy body limit, browser test setup, CI and root docs. Public DTOs and both migration
chains are unchanged. Shared ownership returns to Nai; coordinate subsequent edits there.

M2's `import_cli.py`, `test_normalize.py`, `test_hybrid.py` had pre-existing formatter
failures and receive formatting only. M2 job-database files and algorithm behavior are
not changed. The old test expecting M2's matcher to be missing now tests the actual
matcher and an explicitly simulated import failure.

## Validation evidence

- Locked installation and offline lock consistency checked using the repository environment.
- Backend suite includes real English NLP, parsers and SQLite migrations; explicit opt-in
  model tests additionally use actual pinned weights. Final full suite: **517 passed**, two upstream deprecation warnings (real CPU artifact enabled).
- Ruff lint/format and generated OpenAPI/frontend types checked.
- Browser tests: **3 passed** (upload/progress/profile/evidence/reload; retry/failure;
  unsupported-file error and accessible form labels). HTTP responses use synthetic fixtures.
- Frontend install uses frozen pnpm lock; lint/typecheck/API drift checks pass. Production
  build passes with **Node 24.19.0 / pnpm 11.19.0**.
- Real CPU/local-endpoint parity test passed; see model guide for tolerances and measured
  load time/memory. SageMaker calls in this test use an injected HTTP transport, not AWS.
- Resume API tests cover duplicate inflight uploads, unreadable/oversize files, cross-session
  access, parked retries, ownership of expired leases, transactional intake rollback,
  upload-to-ready with an empty corpus, and new-job refresh without parsing again.

### GitHub CI confirmed

[Run 35248430957](https://github.com/ncwjsp/ai-career-match/actions/runs/35248430957)
passed on code commit `581cbef`: backend, frontend (including all three browser tests),
and PostgreSQL database role/isolation/migration checks. This validates Linux installation
and both migration chains; it does not prove multi-worker concurrency or live AWS behavior.

### Limits that remain

Docker Desktop's engine was unavailable in this run even after attempting startup; the
application tests use SQLite. **PostgreSQL concurrency is not established by those tests.**
CI's two-database job now passes; staging must still check multiple claimants before replicas.
No real resume, AWS credential, S3 bucket, SageMaker endpoint or approved paid resource
was used. No cloud deployment is claimed. Hosting choice, budget, retention confirmation,
live S3/SageMaker verification and operations/orphan cleanup remain shared release gates.
Public CI diagnostics identified the installation blocker: pinned uv could not find Python
3.12.14 in its managed-download list. CI now explicitly installs that exact Python using
actions/setup-python before uv sync. The code commit's successful CI result is linked above.

## M2 can continue now

1. Pull the merged completion branch, or base a dependent branch on it until review merges.
2. Follow the shared embedding version/representation handoff; finish B-03 persisted job
   vectors, exact retrieval, active/expiry filtering and deterministic rebuilds.
3. Finish transformer pair matching and compare all five methods; do not report synthetic
   contract vectors as measured matching quality.
4. Build the permitted manually imported corpus, human labels and LDA/comparison reports.
5. Verify real job import through both trigger directions with the integrated worker.

Manual URL imports, the two databases, 70/30 baseline and required S3/SageMaker scope are
unchanged. There is no scheduled scraper. M2's research and live-source coverage are not
marked complete by this branch.
