"""Job detail read route (B-06).

Not yet mounted into app/api/router.py (M3's step, alongside removing the
jobs planned.py stub -- see app/modules/jobs/router.py). A bare app with just
this router and the same AppError envelope app.main uses is built here rather
than reusing app.main.create_app(): that app already registers
app.api.planned's 501 stub at this exact path, and FastAPI matches the first
route registered for a path, so appending this router afterward would never
be reached (see tests/matching/test_recommendation_router.py for the same
note on that route).
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.contracts.models import ErrorDetail, ErrorResponse
from app.core.container import Container
from app.core.errors import AppError
from app.core.settings import Settings
from app.modules.jobs.router import router as jobs_router
from tests.jobs.factories import make_event, make_job


class WiredContainer(Container):
    """The real container with career_jobs pointed at the test double."""

    def __init__(self, settings, jobs):
        super().__init__(settings=settings)
        self.__dict__["jobs"] = jobs


def _test_app(container: Container, settings: Settings) -> FastAPI:
    application = FastAPI()
    application.state.settings = settings
    application.state.container = container
    application.include_router(jobs_router)

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
def app(job_repository):
    settings = Settings(app_env="test")
    container = WiredContainer(settings, job_repository)
    return _test_app(container, settings)


def test_reads_an_existing_job_by_its_latest_version(app, job_repository):
    job = make_job()
    job_repository.save_with_event(job, make_event())

    response = TestClient(app).get(f"/api/v1/jobs/{job.job_id}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job.job_id
    assert response.json()["content_version"] == 1


def test_reads_the_latest_version_after_an_update(app, job_repository):
    v1 = make_job(content_version=1, title="NLP engineer")
    v2 = make_job(content_version=2, title="Senior NLP engineer")
    job_repository.save_with_event(v1, make_event(job_version=1))
    job_repository.save_with_event(
        v2, make_event(job_version=2, event_id="event-2", event_type="job.updated")
    )

    response = TestClient(app).get(f"/api/v1/jobs/{v1.job_id}")

    assert response.json()["title"] == "Senior NLP engineer"


def test_an_unknown_job_id_is_not_found(app):
    response = TestClient(app).get("/api/v1/jobs/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
