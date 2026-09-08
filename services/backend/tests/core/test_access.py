"""The server-side guard on M2's manual job-import routes (D09)."""

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.access import require_import_access
from app.core.errors import AppError
from app.core.settings import Settings
from app.main import create_app


def app_with_import_route(settings: Settings) -> FastAPI:
    application = create_app(settings)
    router = APIRouter()

    @router.post("/api/v1/jobs/imports", dependencies=[Depends(require_import_access)])
    def stand_in_for_m2_import():
        return {"status": "accepted"}

    application.include_router(router)
    return application


def test_a_valid_team_token_is_accepted():
    app = app_with_import_route(Settings(app_env="test", import_access_tokens="team-a,team-b"))
    response = TestClient(app).post(
        "/api/v1/jobs/imports", headers={"Authorization": "Bearer team-b"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong"},
        {"Authorization": "team-a"},
        {"Authorization": "Basic team-a"},
        {"Authorization": "Bearer "},
    ],
)
def test_anything_else_is_refused(headers):
    app = app_with_import_route(Settings(app_env="test", import_access_tokens="team-a"))
    response = TestClient(app).post("/api/v1/jobs/imports", headers=headers)
    assert response.status_code == 403


def test_an_unconfigured_deployment_keeps_the_import_route_closed():
    app = app_with_import_route(Settings(app_env="test"))
    response = TestClient(app).post(
        "/api/v1/jobs/imports", headers={"Authorization": "Bearer anything"}
    )
    assert response.status_code == 403
    assert "not enabled" in response.json()["error"]["message"]


def test_the_guard_raises_a_typed_application_error():
    assert issubclass(type(AppError()), Exception)
