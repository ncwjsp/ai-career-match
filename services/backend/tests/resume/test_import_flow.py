"""Both persisted databases, the HTTP import boundary and both match triggers."""

from fastapi.testclient import TestClient

from app.core.container import Container
from app.core.settings import Settings
from app.core.storage import LocalObjectStore
from app.main import create_app
from app.modules.resume.worker import ResumeWorker
from app.orchestration.worker import MatchWorker
from scripts.run_worker import load_matcher
from tests.jobs.conftest import job_db_url, job_session_factory  # noqa: F401
from tests.jobs.test_ingest import HTML_V1, HTML_V2, FakeTransport
from tests.nlp.test_embeddings import FixtureEncoder


def test_import_upload_update_and_unchanged_reimport(
    app_session_factory,
    job_session_factory,  # noqa: F811
    clock,
    tmp_path,
    pdf_factory,  # noqa: F811
):
    settings = Settings(app_env="test", import_access_tokens="synthetic-team-token")
    c = Container(settings, clock)
    c.__dict__.update(
        app_sessions=app_session_factory,
        job_sessions=job_session_factory,
        embedding_client=FixtureEncoder(),
        object_store=LocalObjectStore(tmp_path / "objects"),
    )
    transport = FakeTransport()
    c.job_ingestion._transport = transport
    client = TestClient(create_app(settings, c))
    headers = {"Authorization": "Bearer synthetic-team-token"}
    url = "https://job-boards.greenhouse.io/example/jobs/123"
    transport.set(url, 200, "text/html", HTML_V1.encode())
    assert (
        client.post("/api/v1/job-imports", json={"url": url}, headers=headers).json()["new_jobs"]
        == 1
    )
    accepted = client.post(
        "/api/v1/resumes",
        files={
            "file": ("synthetic.pdf", pdf_factory([["Skills", "Python, SQL"]]), "application/pdf")
        },
    ).json()
    resume = ResumeWorker(c)
    match = MatchWorker(c.match_queue, c.match_service(load_matcher(c)), clock, c.dispatcher)
    assert resume.step()
    while match.step():
        pass
    resume.finish_matching()
    assert client.get(accepted["status_url"]).json()["state"] == "ready"
    path = f"/api/v1/candidates/{accepted['candidate_id']}/recommendations"
    first = client.get(path).json()
    assert len(first["results"]) == 1
    job_id = first["results"][0]["job_id"]
    from app.nlp.embeddings import EMBEDDING_VERSION

    assert c.job_embeddings.get(job_id, 1, EMBEDDING_VERSION) is not None

    # A changed posting updates the retained profile without processing another resume.
    transport.set(url, 200, "text/html", HTML_V2.encode())
    changed = client.post("/api/v1/job-imports", json={"url": url}, headers=headers).json()
    assert changed["changed_jobs"] == 1
    while match.step():
        pass
    second = client.get(path).json()
    assert second["revision"] > first["revision"]
    assert second["profile_version"] == first["profile_version"]
    assert second["results"][0]["job_version"] == 2
    assert c.job_embeddings.get(job_id, 2, EMBEDDING_VERSION) is not None
    unchanged = client.post("/api/v1/job-imports", json={"url": url}, headers=headers).json()
    assert unchanged["unchanged_jobs"] == 1
    assert not match.step()
    assert client.get(path).json()["revision"] == second["revision"]
