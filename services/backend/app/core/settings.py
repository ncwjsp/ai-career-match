"""Shared configuration for the API and the worker. Owner: M3 (C-01).

Every cloud-backed adapter has a local counterpart, so a checkout runs, tests
and lints with no AWS account. `object_store_backend` and `embedding_backend`
select which adapter `app.core.storage` / `app.core.inference` build, and
`validate_for_runtime()` refuses a deployment configuration that names a cloud
backend without the settings that backend needs. Secrets are `SecretStr` so a
repr or log line cannot leak them.
"""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """A refused configuration. Raised at startup, never per request."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_mode: Literal["mock", "real"] = "mock"

    app_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://career_app_user:local_app_only@127.0.0.1:5432/career_app"
    )
    job_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://career_jobs_user:local_jobs_only@127.0.0.1:5432/career_jobs"
    )

    # Resume object storage (team revision 2026-09-08: AWS S3 in deployment).
    object_store_backend: Literal["local", "s3"] = "local"
    object_store_local_dir: str = ".local-object-store"
    aws_region: str = "ap-southeast-1"
    resume_bucket: str = ""
    resume_object_prefix: str = "resumes/"
    aws_s3_endpoint_url: str = ""

    # NLP/embedding inference (team revision 2026-09-08: Amazon SageMaker).
    embedding_backend: Literal["local", "sagemaker"] = "local"
    sagemaker_embedding_endpoint: str = ""
    sagemaker_region: str = ""
    sagemaker_timeout_seconds: int = 30

    # Explanation generation (C-02). `fake` is deterministic and offline.
    llm_provider: Literal["fake", "bedrock"] = "fake"
    llm_model_id: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: int = 30

    # Retained-candidate lifecycle (D06). Proposed values, not measured limits.
    profile_retention_days: int = 30
    match_batch_size: int = 100
    max_upload_bytes: int = 10 * 1024 * 1024

    # Manual job-import access guard (D09). Empty keeps the import route closed.
    import_access_tokens: str = ""

    @property
    def sagemaker_region_or_default(self) -> str:
        return self.sagemaker_region or self.aws_region

    @property
    def import_tokens(self) -> frozenset[str]:
        return frozenset(t.strip() for t in self.import_access_tokens.split(",") if t.strip())

    def validate_for_runtime(self) -> None:
        """Refuse a configuration that cannot serve what it claims to serve."""
        if self.app_env == "production" and self.app_mode != "real":
            raise ConfigurationError(
                "Production requires APP_MODE=real; mock adapters must not serve real users."
            )
        if self.app_mode == "real":
            if self.object_store_backend != "s3":
                raise ConfigurationError(
                    "APP_MODE=real requires OBJECT_STORE_BACKEND=s3; the local filesystem "
                    "adapter is not shared between the API and worker processes."
                )
            if self.embedding_backend != "sagemaker":
                raise ConfigurationError("APP_MODE=real requires EMBEDDING_BACKEND=sagemaker.")
            if self.llm_provider == "fake":
                raise ConfigurationError(
                    "APP_MODE=real requires a real LLM provider; `fake` returns fixed text."
                )
        if self.object_store_backend == "s3" and not self.resume_bucket:
            raise ConfigurationError("OBJECT_STORE_BACKEND=s3 requires RESUME_BUCKET.")
        if self.embedding_backend == "sagemaker" and not self.sagemaker_embedding_endpoint:
            raise ConfigurationError(
                "EMBEDDING_BACKEND=sagemaker requires SAGEMAKER_EMBEDDING_ENDPOINT."
            )
        if self.llm_provider != "fake" and not self.llm_model_id:
            raise ConfigurationError("A real LLM provider requires LLM_MODEL_ID.")
        if self.profile_retention_days < 1:
            raise ConfigurationError("PROFILE_RETENTION_DAYS must be at least one day.")
        if self.match_batch_size < 1:
            raise ConfigurationError("MATCH_BATCH_SIZE must be at least one.")
        if self.max_upload_bytes < 1:
            raise ConfigurationError("MAX_UPLOAD_BYTES must be positive.")
