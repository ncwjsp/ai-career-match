# FastAPI API and the matching worker. Owner: M3 (C-06).
#
# One image, two commands: the API serves requests and the worker consumes the
# durable queue. Models and long-running work stay in the worker, so the web
# process never loads one. Build from the repository root:
#   docker build -f infra/backend.Dockerfile -t career-match-backend .
FROM python:3.12.14-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /usr/local/bin/uv

WORKDIR /srv

# Dependencies first, so a source change does not reinstall them. --locked
# fails the build if uv.lock disagrees with pyproject.toml.
COPY services/backend/pyproject.toml services/backend/uv.lock services/backend/.python-version ./
RUN uv sync --locked --no-dev

COPY services/backend/ ./

# Never run as root, and never bake a credential into the image: the database
# URLs, AWS settings and LLM key all arrive as environment variables.
RUN useradd --system --uid 10001 --create-home career
USER career

EXPOSE 8000

# The API. The worker overrides this with:
#   command: ["python", "-m", "scripts.run_worker"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
