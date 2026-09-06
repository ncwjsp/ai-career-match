# Bootstrap handoff — Plai / M1

Prepared 2026-09-06; database verification updated 2026-09-07. SET-01 and initial SET-02 are ready for local review.
No commits or remote exist yet. The staged index is the SET-01 checkpoint;
the remaining changes form SET-02. See [commit instructions](COMMIT_GROUPS.md).

## Evidence

| Check | Result |
| --- | --- |
| Pinned backend sync | Passed with uv.lock; Python 3.12.14 |
| Backend contract/API/fixture tests | **32 passed** |
| Ruff lint and format | Passed after the demo-script formatting fix |
| OpenAPI and frontend generation checks | Passed; both snapshots current |
| Frontend lint and TypeScript | Passed; typecheck generates Next route types first |
| Next production build | Passed |
| Isolated staged SET-01 source snapshot | 3 core backend tests plus lint/format and fresh route generation/TypeScript passed, reusing installed dependencies |
| Live startup | FastAPI and Next started on localhost; health and home returned 200 |
| Frontend-to-backend proxy | Fixture endpoint returned 200 with mode=fixture; planned job endpoint returned expected 501 |
| Two-trigger demonstration | Existing job matched on profile.ready; new job matched against unchanged retained candidate; zero uploads |
| Compose configuration | Validated |
| Online PostgreSQL and migrations | **Passed 2026-09-07**: career_app and career_jobs connect through their respective roles; cross-database access denied; both Alembic upgrade commands succeed and create separate empty version tables |
| GitHub CI | Configured, **not run**; no remote supplied |

Tests cover evidence references, invalid spans/vectors/scores, coherent result
revisions, skill evidence, generated API shapes, structured errors, both matching
triggers, retention opt-out/expiry, stale events, removed/expired jobs and duplicate
queue/pair handling. There are two upstream test-client deprecation warnings;
they do not fail tests. These checks do not establish NLP quality, model
performance, database durability or production readiness.

Docker recovered after Plai reset Desktop. Windows then rejected port 5432
(error 10013), so this checkout's ignored environment files use localhost 15432.
Shared examples/CI keep 5432. The project container is healthy and left running.
The earlier Docker startup blocker is resolved; no project data was deleted by
this verification. No domain schema or production persistence was added.

## Implemented versus mocked

| Area | Implemented now | Deferred owner/task |
| --- | --- | --- |
| Foundation | Next/TS/Tailwind shell, FastAPI health, strict local settings, locked dependencies, CI and owner folders | M3 maintains after review/commit |
| Contracts | Canonical DTOs/ports, generated OpenAPI/TS, typed fixture client | M3 coordinates changes with M1/M2 |
| Resume | Fixed fixture processor only; planned upload/profile endpoints return 501 | Plai: A-01 through A-07 |
| Jobs | Two synthetic postings, memory repository/outbox double, separate DB provisioning config and migration runner | M2: B-01/B-02/B-09 |
| Matching | Fixed pair lookups, independent trigger harness and pair-key upserts | M2: real score/retrieval/ranking/B-10; M3: durable C-08 worker |
| Explanations | Fixed synthetic text and versioned DTO; no model calls | M3: C-02 |
| Storage/workers | Protocols and process-local doubles | M3: C-01/C-08; M2: transactional jobs outbox |
| Results UI | Shell plus generated types/client only | M3: C-03/C-04; Plai: A-06 |
| Cloud/deployment | No resources, accounts, live sources or models configured | SET-03, C-06, INT-02 and release gates |

Mock objects are in `services/backend/app/testing/` and should remain distinct
from production domain adapters. Retained candidates currently live only in a
test process; the new-job demonstration proves contract independence from upload,
not persistence across restarts or published recommendation refresh.

## Ownership transfer

After Plai reviews and commits the two checkpoints, **M3 takes the shared files,
contracts, frontend API types, infrastructure and application database**.
**M2 takes all job database files**, including `alembic-jobs.ini`,
`app/db/jobs/` and `migrations/jobs/`. Plai returns to M1 folders.
This is the documented assignment; teammate acceptance has not been recorded.

- Plai starts A-01 with PDF/DOCX validation and evidence-preserving extraction.
  Ask M3 to merge needed dependencies; do not edit the shared manifest concurrently.
- M2 starts B-09 using the agreed JobRepository/outbox contracts and both example
  jobs. Implement atomic job/event writes and migrations before live ingestion.
  B-01 investigates permitted JobThai/JobsDB/company/API sources.
- M3 starts C-01 with retained profiles, sessions/storage, match queue/repository
  and application migrations. Use FixtureResumeProcessor/FixtureMatcher/
  FixtureExplainer while other modules develop. Replace planned API handlers
  through coordinated route wiring. Complete retry/revision semantics in C-08.

The [ownership map](OWNERSHIP.md) defines exclusive paths. M3 coordinates common
changes through one PR at a time. Each member works in their own feature branch
and records progress evidence in an issue; M3 updates plan.md centrally.

## Remaining bootstrap gates

- Plai reviews both diffs and makes the two commits; record their hashes below.
- M2/M3 review DTOs, evidence spans, version rules, event/repository ports and
  synthetic handoffs. Their acceptance is pending.
- Supply the actual GitHub target, visibility and teammate handles; only then
  configure the remote/collaborators/CODEOWNERS and publish. No remote action was
  authorized for an invented target.
- Run CI on GitHub, record results, then mark the setup tasks Done under the
  plan's Definition of Done. Source/language/model/cloud decisions remain SET-03.

| Checkpoint | Commit hash | Reviewer / date |
| --- | --- | --- |
| SET-01 | Pending Plai's commit | Pending |
| Initial SET-02 | Pending Plai's commit | Pending M2/M3 review |

SET-01 and SET-02 remain **In Progress** in the tracker. All domain implementation
tasks remain **Not Started**; scaffolding and mocks do not complete them.
