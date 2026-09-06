# AI Career Match

Shared bootstrap for a three-person NLP project. Start with plan.md,
START_HERE.md and docs/integration/OWNERSHIP.md.

## Requirements

- Node.js 24.19.0, pnpm 11.19.0
- Python 3.12.14, uv 0.12.2
- Docker Compose for optional local PostgreSQL

## Run locally

From services/backend:

    uv sync --locked
    uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

From apps/web in another terminal:

    pnpm install --frozen-lockfile
    pnpm dev

Open http://127.0.0.1:3000. API docs: http://127.0.0.1:8000/docs.
Default mock mode requires no database, AWS, job-source account or model download.
The shell does not accept uploads. Production mode is intentionally unavailable.

## Optional local PostgreSQL

Copy root .env.example to .env, then run from the repository root:

    docker compose --env-file .env -f infra/compose.yaml up -d --wait
    docker compose --env-file .env -f infra/compose.yaml exec postgres psql -U postgres -d postgres -c "\l"

career_app and career_jobs are distinct databases with different owner roles.
Their connection URLs are in services/backend/.env.example. Copy it to .env
there if you want to customize settings. There are no domain tables yet.
Database initialization runs only on a new volume. Do not delete an existing
volume to change credentials; coordinate an explicit migration.
Stop with docker compose --env-file .env -f infra/compose.yaml stop.

## Checks

From services/backend:

    uv run ruff check .
    uv run ruff format --check .
    uv run pytest

From apps/web:

    pnpm lint
    pnpm typecheck
    pnpm build

Dependencies are locked in services/backend/uv.lock and apps/web/pnpm-lock.yaml.
Use uv sync --locked and pnpm install --frozen-lockfile in CI and after cloning.
Ask M3 to coordinate dependency changes after bootstrap.

## Scope

Implemented here: application shell, health endpoints, ownership scaffolds and
local database provisioning. Real resume NLP (M1), ingestion/ranking (M2), and
persistence/explanations/production workers (M3) remain assigned work.
