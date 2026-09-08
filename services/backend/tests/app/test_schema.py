"""The migration chain, not `create_all`, is what deployment runs."""

from sqlalchemy import inspect

from app.db.app.models import Base

EXPECTED = {
    "sessions",
    "candidates",
    "resume_uploads",
    "candidate_profiles",
    "candidate_embeddings",
    "analysis_runs",
    "work_queue",
    "processed_events",
    "match_runs",
    "match_results",
    "recommendation_revisions",
    "recommendation_entries",
    "explanations",
}


def test_the_migration_creates_every_declared_table(app_session_factory):
    with app_session_factory() as session:
        tables = set(inspect(session.bind).get_table_names())
    assert EXPECTED <= tables
    assert set(Base.metadata.tables) == EXPECTED


def test_no_table_references_the_job_database(app_session_factory):
    with app_session_factory() as session:
        inspector = inspect(session.bind)
        for table in EXPECTED:
            for key in inspector.get_foreign_keys(table):
                assert key["referred_table"] in EXPECTED
