# Start here, Plai

You are **M1 / Plai**. Read [plan.md](plan.md) for the central scope/tracker and [README.md](README.md) for the actual installation and test commands.

## Current checkpoint

The repository is [ncwjsp/ai-career-match](https://github.com/ncwjsp/ai-career-match). SET-01 (`0a00918`) and initial SET-02 (`858c58b`) are published on `main`. Do not recreate or recommit the bootstrap.

A-01 is published at `a8d4c91` on `feat/m1/a-01-resume-parsers`, with recorded evidence of 58 parser tests / 90 total backend tests passing. It is not merged into main yet. M3 must coordinate its shared dependency handoff (`pypdf==6.17.0`, `defusedxml==0.7.1`), review and CI before merging. Its source/tests/docs stay on that feature branch until merge; this scope revision does not copy or replace them.

The bootstrap has shell/health endpoints, synthetic adapters and generated contracts. Product endpoints are planned 501 responses; queues/repositories are in-memory test doubles. Local database startup, separate roles and independent migration runners were verified; real domain tables, import flow, ranking, explanations and deployment remain assigned work. See [historical bootstrap evidence](docs/integration/BOOTSTRAP_HANDOFF.md). Published commits alone do not establish GitHub CI or teammate review.

## Revised scope, 2026-09-07

- A team member pastes a permitted job URL into a small import page. The proposed access rule is team/admin only, pending confirmation before the access contract is frozen.
- Import one posting into `career_jobs`; submit the same URL to refresh it. An unchanged import does not create duplicate events. A failed refresh preserves the previous usable version and reports the error.
- New/changed jobs automatically match retained active candidates through durable events. Candidate users still upload one resume; no additional target-job input is required.
- No cron, recurring scraper or site-discovery crawler is planned. Source links and last successful checks show the limits of manually maintained freshness.
- Deploy Next.js, FastAPI, one CPU worker and one PostgreSQL service hosting `career_app` and `career_jobs`. Use PostgreSQL queues and stored vectors with exact retrieval for the small corpus; no external search cluster is required.
- Keep the 70/30 semantic/required-skill formula, NLP entities/evidence, summaries, grounded explanations, five-method comparison and LDA research. See the full formula and edge cases in the plan.

## Infrastructure revision, 2026-09-08

The team decided to use **AWS S3** for resume object storage and an **Amazon SageMaker** endpoint for NLP/embedding inference. Local filesystem and in-process CPU adapters stay behind the same ports for tests, CI and offline work, and A-07 parity is now local versus SageMaker. OpenSearch and Bedrock stay out of the MVP; retrieval remains stored vectors plus exact cosine, and explanation generation stays provider-neutral.

Where web/API/worker/PostgreSQL run is still open (D07): Railway remains viable, and an AWS-native host is now possible too. Nothing is provisioned. M3 confirms an AWS account owner, region, instance type, endpoint start/stop policy and a budget before any paid setup; a SageMaker endpoint bills per hour while it exists, whether or not it serves traffic. Required environment variables are listed in `services/backend/.env.example`; no key is committed.

## Task orders

Each person works on a separate task branch from current main. Do not wait for Plai to finish all resume NLP: use synthetic profiles, jobs and adapter interfaces.

| Member | Start now | Next | Later |
| --- | --- | --- | --- |
| Plai / M1 | Review A-01 and get M3's dependency PR merged; finish A-01 review/merge | A-02 shared preprocessing/POS/NER/aliases and evidence mapping; then A-03 profile extraction and A-04 embeddings | A-05 routes, A-06 intake/profile UI, A-07 CPU packaging/parity |
| M2 | B-09 job database/outbox; investigate B-01 single-job URL source feasibility | B-02 fixture-backed import service and isolated import UI after M3 freezes contracts; B-04 baselines; B-03 stored-vector retrieval | B-06 skills/APIs, B-10 incremental matching, B-05 advanced ranking, B-07/B-08 research |
| M3 / Nai | Take shared-file ownership; small dependency/import-contract PRs; C-01 application persistence, S3/SageMaker adapters and durable queue | C-03 API client/routes and import access guard; C-08 event dispatch; C-02/C-04 with fixtures | C-05 integration, C-06 deployment with S3/SageMaker, C-07 CI/runbook; INT-01/INT-02 gates |

M2 alone owns `services/backend/app/db/jobs/` and `migrations/jobs/`; M3 owns `app/db/app/` and `migrations/app/`. M2 also owns the planned `apps/web/src/features/job-import/` component and its tests. M3 owns its route mounting, API client, shared UI and access guard. See [ownership](docs/integration/OWNERSHIP.md).

## Clone and branch

A teammate clones once:

```bash
git clone https://github.com/ncwjsp/ai-career-match.git
cd ai-career-match
```

Before each new task, with a clean working tree:

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/m2/b-09-job-database
```

Use the branch appropriate to your task. Do not create A-01 again: it already exists. M1's next branch is `feat/m1/a-02-shared-nlp` after A-01 merges. If independent A-02 work starts earlier, use canonical synthetic ProcessedText fixtures and avoid importing unmerged A-01 internals.

Run README checks, stage explicit owned paths, and open a focused PR with task ID, behavior, limitations and evidence. M3 merges shared contract/dependency changes before dependent feature work, regenerates snapshots/lockfiles, and updates the tracker after receiving evidence. Do not edit another member's files concurrently or mark an open feature branch Done.

## Next prompt for Plai

Use after A-01 is reviewed and merged:

```text
I am Plai (M1). Inspect existing work and read plan.md, START_HERE.md,
the canonical contracts and A-01 extraction docs. Create
feat/m1/a-02-shared-nlp from current main and implement A-02: versioned
shared cleaning/tokenization, POS/NER, skill aliases and evidence mapping.
Preserve technical terms, original evidence coordinates and unknown values.
Follow the agreed language/model scope; document unresolved choices instead
of claiming unsupported language coverage. Work in app/nlp, tests/nlp and
docs/resume; coordinate shared dependency/contract changes with M3.
Use synthetic resume and job fixtures. Keep ranking and job import logic
with M2. Run relevant tests and leave changes ready for review without
committing or pushing.
```

## First prompt for M2

```text
I am M2, the job-data and matching owner. Inspect existing files and read
README.md, START_HERE.md, plan.md and canonical contracts. Create
feat/m2/b-09-job-database from current main; preserve existing work.
Implement B-09 only in app/db/jobs, migrations/jobs and jobs tests/docs:
career_jobs sources, permitted snapshots, normalized jobs and immutable
versions, manual import-run metadata and a transactional job-change outbox.
Use synthetic jobs. Verify idempotency, unchanged versus changed updates,
transaction rollback and separation from career_app. Do not require any
resume upload, cron or live source. Propose necessary shared protocol/DTO
changes to M3 instead of editing them concurrently. Run relevant checks;
leave changes ready for review without committing or pushing.
```

For B-02 afterward, ask M3 to merge the import request/status contract first. Build a single-URL adapter and an import/status component in your own feature folder. Confirm one permitted source works; do not promise JobThai/JobsDB until verified. M3 mounts the page and enforces access. Use fake fetch/NLP/queue adapters while dependencies are unfinished.

## First prompt for M3

```text
I am M3, the shared application/integration owner. Read README.md,
START_HERE.md, plan.md and canonical contracts; inspect and preserve work.
Take the shared-file handoff. First prepare focused shared changes for
A-01 parser dependencies and the new manual URL import request/status/port,
coordinating with M1/M2 and regenerating contracts/types/lockfiles as needed.
Do not combine these changes with a large implementation PR.
Then create feat/m3/c-01-app-persistence from current main and implement
career_app persistence, retained candidate/session scope, profile/match
repositories and PostgreSQL-backed queues/worker lifecycle. Use fake
resume processor and matcher adapters. Prepare C-08 event dispatch with
both matching triggers and no browser or second-upload dependency.
Do not edit M2 job tables/migrations or M1 resume/NLP internals. Plan
web/API/worker/PostgreSQL plus the private S3
bucket and SageMaker endpoint for C-06; there is no cron requirement. Keep paid deployment separate until budget and
target are agreed. Verify recovery/session boundaries; leave focused
changes ready for review without committing or pushing.
```

## First integration gate: INT-01

These are acceptance steps for later implementation, not current capabilities:

1. Import synthetic jobs into `career_jobs` before any candidate exists.
2. Upload one synthetic resume; persist its profile/embedding in `career_app` and get ranked jobs.
3. Record the profile version and close the browser.
4. Submit a new relevant job URL through the protected importer using a fixture fetch adapter; consume the committed event.
5. Reopen the retained session and verify the new job appears without another upload or parser call.
6. Verify identical pair scores in both directions, including the 77.0% worked example. Select a job and check evidence-grounded explanation states.
7. Re-import unchanged content, update requirements, fail a refresh, mark a job closed and restart the worker. Check no duplicates, preserved prior data and correct recovery.
8. Reject unsafe URLs and unauthorized import requests; keep candidate data isolated.

INT-02 repeats the flow on the deployed host with a permitted real URL and the real S3/SageMaker/LLM adapters. Record measured cost, freshness, model memory, latency and limitations. Source coverage is the set of manually imported jobs, not a continuously monitored job market.
