"""Explicit integration check; requires local PostgreSQL to be running."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.core.settings import Settings


def main() -> None:
    settings = Settings()
    for secret, expected, role, other in [
        (settings.app_database_url, "career_app", "career_app_user", "career_jobs"),
        (settings.job_database_url, "career_jobs", "career_jobs_user", "career_app"),
    ]:
        url = make_url(secret.get_secret_value())
        engine = create_engine(url)
        with engine.connect() as connection:
            actual = connection.execute(text("SELECT current_database(), current_user")).one()
            assert actual == (expected, role), f"Unexpected database or role for {expected}"
        engine.dispose()
        other_engine = create_engine(url.set(database=other))
        try:
            with other_engine.connect():
                raise AssertionError(f"{role} must not connect to {other}")
        except OperationalError:
            pass
        finally:
            other_engine.dispose()
        print(f"{expected}: connection and cross-database isolation verified")


if __name__ == "__main__":
    main()
