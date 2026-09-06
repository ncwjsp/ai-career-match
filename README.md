# AI Career Match

A three-person NLP project. This checkout contains the SET-01 shell and initial
SET-02 contracts, synthetic data and test doubles. Start with [plan.md](plan.md),
[START_HERE.md](START_HERE.md) and the [bootstrap handoff](docs/integration/BOOTSTRAP_HANDOFF.md).
Real resume processing, job ingestion, ranking and explanations remain assigned work.

## Requirements

- Node.js **24.19.0**, pnpm **11.19.0**
- Python **3.12.14**, uv **0.12.2**
- Docker Desktop with its Linux engine and Compose, only for local PostgreSQL

Install the listed tools and check their versions first. Runtime files, exact
dependency versions and both lockfiles are committed. Internet access is needed
for the first dependency installation; no AWS credentials or model downloads are
needed for the default mock mode.

## Start locally

In terminal 1, from the repository root:

```bash
cd services/backend
uv sync --locked
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In terminal 2, from the repository root:

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm dev
```

Open http://127.0.0.1:3000. API documentation is at
http://127.0.0.1:8000/docs. Stop either server with Ctrl+C.
The frontend proxies `/backend/*` to FastAPI; no browser CORS setup is necessary.
For a production-build smoke test, stop the frontend, run `pnpm build`, then
`pnpm start`. This verifies the shell; it does not make the backend production ready.

Environment examples use local development values only. Defaults work without
copying an environment file. To customize them, copy `apps/web/.env.example` to
`apps/web/.env.local` or `services/backend/.env.example` to
`services/backend/.env`. Use PowerShell `Copy-Item` or POSIX `cp`.
Keep backend secrets out of variables prefixed with `NEXT_PUBLIC_`.

## What runs now

| Surface | Current behavior |
| --- | --- |
| Web home | Responsive project shell, with upload/recommendations visibly unavailable |
| `GET /health/live` | Process health |
| `GET /health/ready` | Mock readiness; explicitly says external dependencies are not required |
| `GET /dev/fixtures` | Read-only synthetic profile, jobs, scores, events and explanation |
| `/api/v1/*` | Documented contracts; valid requests return structured **501** until owners implement them |
| Invalid planned requests | Structured **422** |
| `APP_ENV=production` | Startup fails intentionally; authentication and real adapters are not implemented |

No user-facing upload flow is implemented. Do not use real resumes with this
bootstrap. Fixture scores are predetermined values, and the explanation is fixed
text. The API is a local development service.

From `services/backend`, demonstrate both matching triggers:

```bash
uv run python -m scripts.demo_handoff
```

Expected: `job-demo-1` is matched after `profile.ready`; adding
`job-demo-2` triggers another match for the same retained profile with **zero
resume uploads**. The fixture pair scores are 77 and 84. The clock is fixed at
2026-09-05 so retention tests remain reproducible. This is an in-memory contract
exercise; durable dispatch, scoring, ordering and revision publication remain
M2/M3 work.

## Local PostgreSQL

Copy the root `.env.example` to root `.env` (do not overwrite an existing file).
Start Docker Desktop's Linux engine, then from the repository root:

```bash
docker compose --env-file .env -f infra/compose.yaml config --quiet
docker compose --env-file .env -f infra/compose.yaml up -d --wait --wait-timeout 120
```

One pinned PostgreSQL container creates two independent databases:

| Database | Owner role | Schema/migration owner |
| --- | --- | --- |
| `career_app` | `career_app_user` | M3: `app/db/app/`, `migrations/app/`, `alembic-app.ini` |
| `career_jobs` | `career_jobs_user` | M2: `app/db/jobs/`, `migrations/jobs/`, `alembic-jobs.ini` |

Application and job credentials are separate. The initialization script revokes
public connection access to both databases and grants each owner its own access.
Only localhost exposes the PostgreSQL port. There are no domain tables yet.

From `services/backend`:

```bash
uv run python -m scripts.check_databases
uv run alembic -c alembic-app.ini upgrade head
uv run alembic -c alembic-jobs.ini upgrade head
```

The check connects using each role and verifies that it cannot connect to the
other database. Each Alembic command uses its own URL and migration history.
M3 and M2 will add their domain metadata before using Alembic autogeneration.
If passwords or the host port change in root `.env`, update the corresponding
backend URLs too; URL-encode special characters in passwords.

Initialization runs only on an empty volume. Changing environment values will
not update existing database passwords. Do not delete a populated volume to
change configuration; coordinate a database change with the owner.

From the repository root, stop services without deleting data:

```bash
docker compose --env-file .env -f infra/compose.yaml stop
```

**Verified locally on 2026-09-07:** both databases start, each owner connects only
to its own database, and both Alembic upgrade commands pass. Each database has
its own empty migration-version table; domain tables are still assigned work.
CI includes these checks but has not run on GitHub yet.

This checkout uses **127.0.0.1:15432** because Windows rejected binding port 5432
with error 10013. Root `.env` and `services/backend/.env` are aligned to 15432;
both are ignored by Git. Shared examples and CI retain the default port 5432.
If the default port is unavailable on another machine, choose a free local port,
set `POSTGRES_PORT` in root `.env`, and update the port in both backend database
URLs before starting Compose. No system networking settings need changing.

## Contracts and generated types

Edit Python DTOs in `services/backend/app/contracts/models.py`; interfaces live
next to them in `interfaces.py`. After the bootstrap review/commit, **M3 is the
single editor** for these files. M1/M2 propose changes with producer/consumer
examples. See the [contract guide](contracts/README.md).

From `services/backend`, then `apps/web`, respectively:

```bash
uv run python -m scripts.export_openapi
```

```bash
pnpm api:generate
```

Commit the DTO change, `contracts/openapi.json`,
`apps/web/src/lib/api/generated.ts` and affected fixtures together.
Never edit generated files by hand. Internal Python protocols are not HTTP APIs.
The frontend client obtains its DTO aliases from the generated types.

## Checks

From `services/backend`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m scripts.export_openapi --check
uv run python -m scripts.demo_handoff
```

From `apps/web`:

```bash
pnpm api:check
pnpm lint
pnpm typecheck
pnpm build
```

`typecheck` generates Next route types before running TypeScript, including on a
fresh checkout. Next's `next-env.d.ts` and `.next/` outputs stay ignored.
CI repeats code, fixture, schema/type drift and database checks on pushes/PRs.

## Working independently

- **Plai / M1:** start A-01 in `feat/m1/a-01-resume-parsers`.
- **M2:** start B-09 in `feat/m2/b-09-job-database`; investigate permitted sources
  for B-01. JobThai/JobsDB are candidate sources, not approved integrations.
- **M3:** start C-01 in `feat/m3/c-01-app-persistence`; take custody of shared
  config/contracts and route wiring after review/commit.

Use the [ownership map](docs/integration/OWNERSHIP.md) and teammate prompts in
START_HERE.md. M3 alone updates shared manifests, generated contracts, CI and the
central tracker after handoff. M2 owns the job migration chain; M3 owns the
application chain. Use fixture adapters until the other owner's implementation
is ready. Keep dependency changes in a separate reviewed PR and regenerate the
appropriate lockfile.

The [two commit groups](docs/integration/COMMIT_GROUPS.md) are prepared for Plai's
review. No commit, remote repository or push has been made.
