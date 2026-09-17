FROM ghcr.io/astral-sh/uv:0.12.2 AS uv
FROM python:3.12.14-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/app
COPY services/backend/pyproject.toml services/backend/uv.lock ./
RUN uv sync --locked --extra ml --no-dev
COPY services/backend/app ./app
COPY ml/resume/serve.sh /usr/local/bin/serve
RUN chmod +x /usr/local/bin/serve
ENV PATH="/opt/app/.venv/bin:$PATH" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MODEL_DIR=/opt/ml/model
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/serve"]
