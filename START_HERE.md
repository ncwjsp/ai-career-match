# Start here, Plai

You are **M1 / Plai**. Your long-term work is resume parsing, candidate NLP, shared text/embedding utilities, and the upload/profile UI. First, prepare a small shared foundation so your friends can clone the same contracts and develop independently.

**Current state:** SET-01 and initial SET-02 are implemented locally, with 32 backend tests passing and frontend build/type checks passing. Git is initialized with SET-01 staged and SET-02 left as working changes for your review. No commits or remote exist. Both databases, role isolation and independent migration runners are now verified locally on port 15432 (2026-09-07); shared examples retain 5432. Read [bootstrap evidence](docs/integration/BOOTSTRAP_HANDOFF.md) and follow the exact [two-commit instructions](docs/integration/COMMIT_GROUPS.md); do not stage everything before the first commit.

## 1. Review the prepared shared foundation

Do **SET-01 and the initial SET-02 before A-01**. You temporarily own shared files for these two commits. After they land on `main`, M3 takes over shared configuration/contracts, M2 takes the job database, and you focus on your M1 folders. Teammates can review the foundation as you build it; their implementation branches should start from the published checkpoint.

| Checkpoint | Commit suggestion | What must be available |
| --- | --- | --- |
| 1. Runnable skeleton | `chore: bootstrap shared project foundation (SET-01)` | Next.js/TypeScript/Tailwind shell; minimal FastAPI health endpoint; version-pinned dependency manifests/lockfiles; feature/module folders; `.gitignore`, `.gitattributes`, safe `.env.example`; local database setup; README install/run/check commands; minimal CI. |
| 2. Shared contracts and handoff | `feat: define v1 contracts and fixtures (SET-02)` | Canonical profile/job/match/event DTOs and interfaces; generated OpenAPI/frontend types; synthetic fixtures; tests checking interface/fixture compatibility; ownership map and teammate starting tasks. |

Bootstrap details:

- Use a single backend package with separate resume, jobs, matching, explanation, and orchestration folders as defined in `plan.md`.
- Provide `APP_DATABASE_URL` for `career_app` and `JOB_DATABASE_URL` for `career_jobs`. One local PostgreSQL container may host both databases. Initialize databases/roles in infrastructure; keep application/job tables and migration histories owned by M3/M2 respectively.
- Include retained candidate/profile versions, `MatchRun`, job-change events, and recommendation revisions in contracts. Matching must not depend on an upload request being active.
- Publish `score_pair(profile, job, scoring_version)` and batch matching interfaces. The initial formula is `100 * (0.70 * semantic_similarity + 0.30 * required_skill_coverage)`; use the full edge-case rules in `plan.md`.
- Include fake profiles/jobs/events so friends need no resume uploads, job-source credentials, AWS account, or model download to start their component tests. A fake response must be visibly identified as a fixture.
- Implement only the shell/health endpoint and useful contract checks during bootstrap. Do not build friends' ranking, scraping, database domain models, or generation features. Planned endpoints are not complete until their handlers are implemented; scaffolds must not return misleading success.
- Add owner comments or a Markdown ownership map until real GitHub handles are known. Configure CODEOWNERS after the handles are supplied; do not invent identities.
- Put actual run/test commands in README after verifying them. Do not claim a fresh clone works based only on directory creation.
- Record what is working, what is mocked, remaining decisions, and the bootstrap commit in the handoff. SET-03 cloud/live-source decisions can continue afterward; they must not block fixture-based collaboration.

Original bootstrap request (retained for scope/reference; do not rerun it over the prepared work):

```text
I am Plai (M1). Read plan.md and START_HERE.md, then implement the shared
bootstrap for SET-01 and initial SET-02 in this repository. Inspect existing
files first and preserve any changes already present.

Create a minimal runnable Next.js/TypeScript/Tailwind shell and FastAPI
backend, the planned ownership folders, pinned dependency workflows, safe
environment examples, local PostgreSQL setup with separate career_app and
career_jobs databases, README commands, and minimal CI.

Define canonical profile/job/evidence/match/event contracts, repository and
worker interfaces, generated API/frontend types, and small synthetic fixtures.
Model both profile-ready matching and new-job matching against retained
candidates. Use independent application/job migration folders. Provide mock
adapters so all members can develop without AWS or live job-source access.

Verify startup and useful contract/fixture tests. Keep real resume NLP,
scraping, ranking, and explanations for their assigned members. Record what
is implemented versus mocked, and prepare two focused commit groups for
SET-01 and SET-02. Update tracker statuses only from actual evidence.
After bootstrap, hand shared files/contracts to M3 and job DB files to M2.
Do not create a remote repository or push without an actual target supplied
by me. Leave changes ready for my review and commit.
```

## 2. Commit and publish the foundation

Run the README checks and review changed files. Git is already initialized on `main`; do not reinitialize it. The staged index contains the SET-01 snapshot. Review `git diff --cached` and commit that checkpoint first. Only afterward stage the contract/handoff changes for SET-02. No secrets, real resumes, downloaded corpora or model weights belong in either commit. See [COMMIT_GROUPS.md](docs/integration/COMMIT_GROUPS.md) for the exact commands. After both commits, you can immediately start A-01; your friends can start B-09 and C-01 from the same checkpoint once it is shared.

Create an **empty** GitHub repository under your chosen account/organization, select its visibility, and add your two friends as collaborators. Replace `YOUR_GITHUB_URL` below with its actual HTTPS or SSH clone URL:

```bash
git remote add origin YOUR_GITHUB_URL
git push -u origin main
```

If `origin` already exists, inspect `git remote -v` and use the existing intended remote instead of adding another one. GitHub authentication and a Git author identity must be configured on each person's computer; use each person's own identity. These steps follow [GitHub's existing-project upload guide](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

After bootstrap is published, share the repository URL and commit hash. Teammates each clone it once:

```bash
git clone YOUR_GITHUB_URL
cd ai-career-match
```

They should read README, this guide, and their section in `plan.md`, then run the verified setup checks. From the shared checkpoint, each person creates a separate task branch. For subsequent tasks, first update `main` with `git pull --ff-only origin main`.

## 3. Start three independent branches

| Member | First branch | First useful deliverable |
| --- | --- | --- |
| Plai / M1 | `feat/m1/a-01-resume-parsers` | PDF/DOCX extraction into the shared text/evidence contract using safe local test fixtures. |
| M2 / suggested Baibua | `feat/m2/b-09-job-database` | Job database models/migrations/repository and outbox, with a fixture ingestion test. Investigate permitted sources in parallel. |
| M3 / suggested Nai | `feat/m3/c-01-app-persistence` | Application database, retained candidate/session data, match queue/repository, and mock worker integration. |

You do not need to finish the resume feature before your friends start. M2 uses the committed synthetic profiles; M3 uses fake processor/matcher implementations. Replace mocks at integration without changing contracts unilaterally.

### Your next prompt after bootstrap

```text
I am Plai (M1). Read plan.md and the committed bootstrap contracts. Work on
feat/m1/a-01-resume-parsers and implement A-01: PDF/DOCX validation and text
extraction with evidence references and clear unreadable-file errors.
Use synthetic fixtures and the existing test/dependency setup. Own only the
resume module, its tests, and docs/resume. Do not put matching logic in the
upload/parser code. Report any needed shared contract/dependency changes
for M3 to coordinate. Run relevant tests and leave a focused commit-ready
change with the task ID and implementation limitations.
```

### Prompt for M2 after cloning

```text
I am Member 2 (job data and matching owner). Read README.md, START_HERE.md,
plan.md, and the current contracts. Do not recreate the bootstrap. Create
feat/m2/b-09-job-database from the published main checkpoint.

Implement B-09 in app/db/jobs, migrations/jobs, and jobs tests: use the
separate career_jobs database; store sources, permitted job snapshots,
normalized jobs/versions, ingestion runs, and a transactional job-change
outbox. Use the agreed interfaces and fixture jobs; do not require resumes
or write candidate tables. Verify idempotent writes and event rollback.

Keep app/db/app, application migrations, root config, public contracts,
and UI files with M3. Document any change requests instead of editing those
files concurrently. Next work is fixture ingestion B-02 and the shared
scoring/incremental matching path B-04/B-06/B-10, so newly collected jobs
can match stored candidate profiles. Run relevant checks and produce a
focused PR/commit-ready change with evidence and outstanding dependencies.
```

### Prompt for M3 after cloning

```text
I am Member 3 (application integration and explanations owner). Read
README.md, START_HERE.md, plan.md, and the published contracts. Confirm
the bootstrap handoff and create feat/m3/c-01-app-persistence. Do not
recreate the scaffold or modify M1/M2 domain files.

Implement C-01 in app/db/app, migrations/app, core and orchestration:
career_app persistence, retained candidate/session scope, profile and
match repositories, durable queues and useful worker states. Use fake
resume processor/matcher adapters so Plai and M2 can keep working.

Prepare C-08's job-event dispatcher interface and revision publication
without editing M2's job database/migrations. Model matching triggered
both by profile-ready and by newly ingested jobs, without a second upload
or an open browser. Own shared contracts/configuration after this handoff;
coordinate changes with both consumers. Verify persistence/recovery/session
boundaries and leave a focused PR/commit-ready change with test evidence.
```

## 4. First team integration check

Keep these as acceptance steps for INT-01; they are not claimed to work at bootstrap:

1. Ingest fixture jobs into `career_jobs` before any resume upload.
2. Upload a safe sample resume once; persist its profile in `career_app` and produce ranked jobs.
3. Record the profile version and close the browser.
4. Insert a new relevant fixture job through ingestion; consume its durable change event and run matching.
5. Reopen the same retained candidate session. The relevant job appears in the updated ranked set without another upload or parser invocation.
6. Check identical pair scores from both matching triggers, including the 77.0% worked example in `plan.md`.
7. Replay the event, change/expire the job, and restart the worker; verify stable results, no duplicates, and correct recovery.

After each feature PR, the owner provides task status and test evidence; M3 serializes plan updates. Use PRs into `main`, avoid direct changes in another member's folders, and merge shared-contract changes before the dependent implementations.
