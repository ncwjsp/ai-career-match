"""C-05: the explanation routes, their access rules and their states."""

import pytest
from fastapi.testclient import TestClient

from app.core.access import SESSION_COOKIE
from app.core.container import Container
from app.core.settings import Settings
from app.db.app.matches import SqlRecommendationRepository
from app.db.app.profiles import SqlProfileRepository
from app.db.app.sessions import SqlSessionStore
from app.main import create_app
from app.testing.memory import MemoryJobs
from tests.app.factories import make_profile, make_recommendation_set
from tests.jobs.factories import make_job

PATH = "/api/v1/candidates/{candidate}/recommendations/1/jobs/job-1/explanation"


class WiredContainer(Container):
    """The real container with the two databases replaced by the test doubles."""

    def __init__(self, settings, clock, app_sessions, jobs):
        super().__init__(settings=settings, clock=clock)
        self.__dict__["app_sessions"] = app_sessions
        self.__dict__["jobs"] = jobs


@pytest.fixture
def wired(app_session_factory, clock):
    jobs = MemoryJobs([make_job("job-1"), make_job("job-2")])
    container = WiredContainer(Settings(app_env="test"), clock, app_session_factory, jobs)
    sessions = SqlSessionStore(app_session_factory, clock)
    session_id, candidate_id = sessions.start()
    SqlProfileRepository(app_session_factory, clock).save(make_profile(candidate_id))
    SqlRecommendationRepository(app_session_factory, clock).publish(
        make_recommendation_set(candidate_id, jobs=("job-1", "job-2"))
    )
    app = create_app(Settings(app_env="test"), container)
    return {"app": app, "session_id": session_id, "candidate_id": candidate_id}


def client(wired, authenticated=True):
    test_client = TestClient(wired["app"])
    if authenticated:
        test_client.cookies.set(SESSION_COOKIE, wired["session_id"])
    return test_client


def test_an_explanation_is_generated_for_a_ranked_job(wired):
    response = client(wired).post(PATH.format(candidate=wired["candidate_id"]))
    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "ready"
    assert body["prompt_version"] == "explain-v1"
    assert body["job_id"] == "job-1"


def test_reading_before_generating_reports_pending_with_real_evidence(wired):
    response = client(wired).get(PATH.format(candidate=wired["candidate_id"]))
    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "pending"
    assert body["text"] is None
    assert body["strengths"] == ["Strong Python experience"]


def test_a_generated_explanation_is_readable_afterwards(wired):
    session = client(wired)
    session.post(PATH.format(candidate=wired["candidate_id"]))
    response = session.get(PATH.format(candidate=wired["candidate_id"]))
    assert response.status_code == 200
    assert response.json()["state"] == "ready"


def test_another_session_cannot_read_this_candidates_explanation(wired):
    response = client(wired, authenticated=False).post(PATH.format(candidate=wired["candidate_id"]))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_an_unknown_revision_is_not_found(wired):
    path = f"/api/v1/candidates/{wired['candidate_id']}/recommendations/9/jobs/job-1/explanation"
    assert client(wired).post(path).status_code == 404


def test_a_job_outside_the_revision_is_not_found(wired):
    path = f"/api/v1/candidates/{wired['candidate_id']}/recommendations/1/jobs/job-404/explanation"
    assert client(wired).post(path).status_code == 404


def test_the_planned_routes_owned_by_m1_and_m2_still_report_501(wired):
    response = client(wired).get(f"/api/v1/candidates/{wired['candidate_id']}/recommendations")
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"
