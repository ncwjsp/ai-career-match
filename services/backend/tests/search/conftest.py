"""Reuses tests/jobs' career_jobs fixtures. Owner: M2 (B-03).

Fixtures are scoped to the directory that defines them and its subtree, so
tests/search (a sibling of tests/jobs) cannot see tests/jobs/conftest.py's
fixtures without this import -- a standard pytest cross-directory reuse
pattern, not a redefinition.
"""

from tests.jobs.conftest import (  # noqa: F401
    job_db_url,
    job_embedding_repository,
    job_repository,
    job_session_factory,
)
