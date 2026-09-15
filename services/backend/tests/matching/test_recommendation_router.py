"""Recommendations read route (B-06).

Not yet mounted into app/api/router.py (M3's step, alongside removing the
matching planned.py stub -- see app/modules/matching/router.py). A bare app
with just this router and the same AppError envelope app.main uses is built
here rather than reusing app.main.create_app(): that app already registers
app.api.planned's 501 stub at this exact path, and FastAPI matches the first
route registered for a path, so appending this router afterward would never
be reached.
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.contracts.models import ErrorDetail, ErrorResponse
from app.core.access import SESSION_COOKIE
from app.core.container import Container
from app.core.errors import AppError
from app.core.settings import Settings
from app.db.app.matches import SqlRecommendationRepository
from app.db.app.profiles import SqlProfileRepository
from app.db.app.sessions import SqlSessionStore
from app.modules.matching.router import router as matching_router
from tests.app.factories import make_profile, make_recommendation_set


class WiredContainer(Container):
    """The real container with career_app pointed at the test database."""

    def __init__(self, settings, clock, app_sessions):
        super().__init__(settings=settings, clock=clock)
        self.__dict__["app_sessions"] = app_sessions


def _test_app(container: Container, settings: Settings) -> FastAPI:
    """The same AppError -> ErrorResponse envelope app.main.create_app uses,
    minus the rest of the application -- this router is not wired in yet."""
    application = FastAPI()
    application.state.settings = settings
    application.state.container = container
    application.include_router(matching_router)

    @application.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        body = ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                request_id=str(uuid4()),
            )
        )
        return JSONResponse(status_code=exc.status, content=body.model_dump(mode="json"))

    return application


@pytest.fixture
def wired(app_session_factory, clock):
    settings = Settings(app_env="test")
    container = WiredContainer(settings, clock, app_session_factory)
    sessions = SqlSessionStore(app_session_factory, clock)
    session_id, candidate_id = sessions.start()
    SqlProfileRepository(app_session_factory, clock).save(make_profile(candidate_id))
    app = _test_app(container, settings)
    return {"app": app, "session_id": session_id, "candidate_id": candidate_id}


def client(wired, authenticated=True):
    test_client = TestClient(wired["app"])
    if authenticated:
        test_client.cookies.set(SESSION_COOKIE, wired["session_id"])
    return test_client


def path(candidate_id: str) -> str:
    return f"/api/v1/candidates/{candidate_id}/recommendations"


def test_reads_the_latest_published_recommendation_set(wired, app_session_factory, clock):
    SqlRecommendationRepository(app_session_factory, clock).publish(
        make_recommendation_set(wired["candidate_id"], jobs=("job-1", "job-2"))
    )

    response = client(wired).get(path(wired["candidate_id"]))

    assert response.status_code == 200
    body = response.json()
    assert [r["job_id"] for r in body["results"]] == ["job-1", "job-2"]
    assert body["candidate_id"] == wired["candidate_id"]


def test_no_published_recommendations_yet_is_not_found(wired):
    response = client(wired).get(path(wired["candidate_id"]))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_a_republished_revision_is_read_back(wired, app_session_factory, clock):
    repo = SqlRecommendationRepository(app_session_factory, clock)
    repo.publish(make_recommendation_set(wired["candidate_id"], revision=1, jobs=("job-1",)))
    repo.publish(
        make_recommendation_set(wired["candidate_id"], revision=2, jobs=("job-2", "job-1"))
    )

    body = client(wired).get(path(wired["candidate_id"])).json()

    assert body["revision"] == 2
    assert [r["job_id"] for r in body["results"]] == ["job-2", "job-1"]


def test_another_session_cannot_read_this_candidates_recommendations(wired):
    response = client(wired, authenticated=False).get(path(wired["candidate_id"]))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_an_unauthorized_candidate_id_is_forbidden_not_leaked_as_not_found(wired):
    # A candidate id that does not belong to this session -- known or not --
    # must read the same as an unknown one, so a caller cannot probe ids.
    response = client(wired).get(path("someone-elses-candidate-id"))

    assert response.status_code == 403
