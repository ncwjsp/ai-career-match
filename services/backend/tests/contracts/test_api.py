import pytest
from fastapi.testclient import TestClient

from app.contracts.models import ErrorResponse, FixtureBundle
from app.core.settings import Settings
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(Settings(app_env="test"))) as instance:
        yield instance


def test_development_endpoint_is_explicitly_synthetic(client):
    response = client.get("/dev/fixtures")
    assert response.status_code == 200
    bundle = FixtureBundle.model_validate(response.json())
    assert bundle.mode == "fixture"
    assert all(job.data_origin == "fixture" for job in bundle.jobs)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analyses/analysis-demo",
        "/api/v1/resumes/resume-demo/profile",
        "/api/v1/candidates/candidate-demo/recommendations",
        "/api/v1/jobs/job-demo-1",
    ],
)
def test_planned_features_never_masquerade_as_working_routes(client, path):
    """Uploads and the profile read belong to A-05; jobs/recommendations to B-06."""
    response = client.get(path)
    assert response.status_code == 501
    assert ErrorResponse.model_validate(response.json()).error.code == "NOT_IMPLEMENTED"


def test_the_implemented_explanation_route_refuses_an_unscoped_session(client):
    """C-02 is implemented, so this route answers with access control, not 501."""
    path = "/api/v1/candidates/candidate-demo/recommendations/1/jobs/job-demo-1/explanation"
    response = client.get(path)
    assert response.status_code == 403
    assert ErrorResponse.model_validate(response.json()).error.code == "FORBIDDEN"


def test_upload_is_not_parsed_or_reported_as_successful(client):
    response = client.post(
        "/api/v1/resumes", files={"file": ("synthetic.txt", b"fixture only", "text/plain")}
    )
    assert response.status_code == 501
    assert client.post("/api/v1/resumes").status_code == 422
    error = client.post("/api/v1/resumes").json()
    assert ErrorResponse.model_validate(error).error.code == "INVALID_REQUEST"


def test_openapi_exposes_shared_dtos_and_candidate_scoped_results(client):
    schema = client.get("/openapi.json").json()
    assert "/api/v1/candidates/{candidate_id}/recommendations" in schema["paths"]
    assert "/api/v1/analyses/{analysis_id}/recommendations" not in schema["paths"]
    for name in [
        "CandidateProfile",
        "JobPosting",
        "EvidenceRef",
        "MatchResult",
        "ProfileReadyEvent",
        "JobChangeEvent",
        "MatchRun",
        "RecommendationSet",
    ]:
        assert name in schema["components"]["schemas"]
