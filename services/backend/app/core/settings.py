from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_mode: Literal["mock"] = "mock"
    app_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://career_app_user:local_app_only@127.0.0.1:5432/career_app"
    )
    job_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://career_jobs_user:local_jobs_only@127.0.0.1:5432/career_jobs"
    )
