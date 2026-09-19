from fastapi.testclient import TestClient

from app.contracts.models import IngestionReport
from app.core.container import Container
from app.core.settings import Settings
from app.main import create_app
from app.modules.jobs.ingest import UnsupportedSourceError


class Importer:
    def __init__(self):
        self.urls = []

    def import_url(self, url):
        if not url.startswith("https://job-boards.greenhouse.io/"):
            raise UnsupportedSourceError("Unsupported source")
        self.urls.append(url)
        return IngestionReport(
            run_id="run-1",
            new_jobs=1,
            changed_jobs=0,
            unchanged_jobs=0,
            event_ids=["event-1"],
            warnings=[],
        )


def test_import_requires_token_and_calls_service_once():
    settings = Settings(app_env="test", import_access_tokens="test-team-token")
    c = Container(settings)
    importer = Importer()
    c.__dict__["job_ingestion"] = importer
    client = TestClient(create_app(settings, c))
    body = {"url": "https://job-boards.greenhouse.io/example/jobs/123"}
    for headers in ({}, {"Authorization": "Bearer wrong"}):
        assert client.post("/api/v1/job-imports", json=body, headers=headers).status_code == 403
    assert importer.urls == []
    headers = {"Authorization": "Bearer test-team-token"}
    response = client.post("/api/v1/job-imports", json=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["new_jobs"] == 1
    assert response.headers["cache-control"] == "no-store"
    assert importer.urls == [body["url"]]
    assert (
        client.post(
            "/api/v1/job-imports", json={"url": "https://example.com"}, headers=headers
        ).status_code
        == 422
    )
