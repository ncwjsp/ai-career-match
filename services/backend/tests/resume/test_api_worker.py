import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.container import Container
from app.core.settings import Settings
from app.core.storage import LocalObjectStore
from app.db.app.models import AnalysisRunRow, ResumeUploadRow, WorkQueueRow
from app.main import create_app
from app.modules.resume.worker import ResumeWorker, event_id
from app.testing.memory import MemoryJobs
from tests.nlp.test_embeddings import FixtureEncoder


@pytest.fixture
def intake(app_session_factory, clock, tmp_path):
    c = Container(Settings(app_env="test"), clock)
    c.__dict__.update(
        app_sessions=app_session_factory,
        object_store=LocalObjectStore(tmp_path / "objects"),
        embedding_client=FixtureEncoder(),
        jobs=MemoryJobs([]),
    )
    return c, TestClient(create_app(c.settings, c))


def upload(client, data):
    return client.post(
        "/api/v1/resumes", files={"file": ("synthetic.pdf", data, "application/pdf")}
    )


def test_upload_profile_and_retained_candidate(intake, pdf_factory):
    c, client = intake
    response = upload(client, pdf_factory([["Skills", "Python, C++, PyTorch"]]))
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert "HttpOnly" in response.headers["set-cookie"]
    worker = ResumeWorker(c)
    assert worker.step()
    assert c.analyses.get(accepted["analysis_id"]).state == "matching"
    profile = client.get(f"/api/v1/resumes/{accepted['resume_id']}/profile")
    assert profile.status_code == 200
    assert "Python" in [s["name"] for s in profile.json()["skills"]]
    assert c.match_queue.claim().event_id == event_id(accepted["analysis_id"])
    # Replay processing after a crash: profile and event are not duplicated.
    run = c.analyses.get(accepted["analysis_id"])
    worker.process(run, c.uploads.file_for(accepted["resume_id"]))
    assert c.profiles.get(accepted["candidate_id"]).profile_version == 1
    with c.app_sessions() as session:
        assert (
            len(list(session.scalars(select(WorkQueueRow).where(WorkQueueRow.queue == "match"))))
            == 1
        )


def test_reads_do_not_cross_session(intake, pdf_factory):
    c, client = intake
    accepted = upload(client, pdf_factory([["Skills", "Python, C++, PyTorch"]])).json()
    ResumeWorker(c).step()
    other = TestClient(create_app(c.settings, c))
    assert other.get(accepted["status_url"]).status_code == 403
    other_id = upload(other, pdf_factory([["Skills", "Python, C++, PyTorch"]])).json()
    assert other_id["candidate_id"] != accepted["candidate_id"]
    assert other.get(accepted["status_url"]).status_code == 404
    assert other.get(f"/api/v1/resumes/{accepted['resume_id']}/profile").status_code == 404


def test_unreadable_file_is_terminal_and_private(intake, pdf_factory):
    c, client = intake
    accepted = upload(client, pdf_factory(image_only=True)).json()
    ResumeWorker(c).step()
    run = client.get(accepted["status_url"]).json()
    assert run["state"] == "failed"
    assert run["error"]["code"] == "NO_EXTRACTABLE_TEXT"
    assert c.profiles.get(accepted["candidate_id"]) is None


def test_rejects_invalid_and_oversized_upload_before_storage(intake):
    c, client = intake
    assert upload(client, b"not a PDF").status_code == 422
    c.settings.max_upload_bytes = 3
    assert upload(client, b"four").status_code == 413
    with c.app_sessions() as session:
        assert list(session.scalars(select(ResumeUploadRow))) == []


def test_no_second_inflight_upload_and_compensates_storage(intake, pdf_factory):
    c, client = intake
    assert upload(client, pdf_factory([["Skills", "Python, C++, PyTorch"]])).status_code == 202
    assert upload(client, pdf_factory([["Skills", "Python, C++, PyTorch"]])).status_code == 409
    with c.app_sessions() as session:
        assert len(list(session.scalars(select(AnalysisRunRow)))) == 1
    assert len([p for p in c.object_store._root.rglob("*") if p.is_file()]) == 1


def test_expired_candidate_is_not_processed(intake, pdf_factory):
    c, client = intake
    accepted = upload(client, pdf_factory([["Skills", "Python, C++, PyTorch"]])).json()
    c.clock.advance(31 * 86400)
    ResumeWorker(c).step()
    assert c.analyses.get(accepted["analysis_id"]).state == "failed"
    assert c.profiles.get(accepted["candidate_id"]) is None


def test_parked_dependency_failure_is_visible(intake, pdf_factory):
    from app.core.inference import DeterministicEmbeddingClient

    c, client = intake
    c.__dict__["embedding_client"] = DeterministicEmbeddingClient()
    accepted = upload(client, pdf_factory([["Skills", "Python, C++, PyTorch"]])).json()
    worker = ResumeWorker(c)
    for _ in range(5):
        worker.step()
        c.clock.advance(31)
    assert c.analyses.get(accepted["analysis_id"]).state == "failed"
    assert c.match_queue.claim() is None


def test_upload_to_results_and_second_resume_with_empty_corpus(intake, pdf_factory):
    from app.modules.matching.scoring import Matcher
    from app.orchestration.worker import MatchWorker

    c, client = intake
    first = upload(client, pdf_factory([["Skills", "Python, SQL"]])).json()
    resume_worker = ResumeWorker(c)
    matcher = Matcher(embedding_client=c.embedding_client, clock=c.clock)
    match_worker = MatchWorker(c.match_queue, c.match_service(matcher), c.clock)
    assert resume_worker.step()
    assert match_worker.step()
    resume_worker.finish_matching()
    assert client.get(first["status_url"]).json()["state"] == "ready"
    second = upload(client, pdf_factory([["Skills", "Java, SQL"]])).json()
    assert first["candidate_id"] == second["candidate_id"]
    assert resume_worker.step()
    assert match_worker.step()
    resume_worker.finish_matching()
    assert client.get(second["status_url"]).json()["state"] == "ready"
    assert c.recommendations.latest(first["candidate_id"]).profile_version == 2


def test_request_limit_applies_before_multipart_storage(intake):
    _, client = intake
    result = upload(client, b"x" * (11 * 1024 * 1024))
    assert result.status_code == 413
    assert result.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_expired_lease_cannot_be_renewed_or_acknowledged_by_old_worker(intake, pdf_factory):
    c, client = intake
    accepted = upload(client, pdf_factory()).json()
    assert c.analysis_queue.claim("old")
    maintenance = c.analysis_queue.maintenance
    assert maintenance.renew(accepted["analysis_id"], "old")
    c.clock.advance(301)
    assert c.analysis_queue.claim("new")
    assert not maintenance.renew(accepted["analysis_id"], "old")
    maintenance.acknowledge(accepted["analysis_id"], "old")
    maintenance.retry(accepted["analysis_id"], "old error", "old")
    with c.app_sessions() as session:
        row = session.get(WorkQueueRow, accepted["analysis_id"])
        assert row.state == "inflight"
        assert row.lease_owner == "new"


def test_failed_intake_rolls_back_metadata_and_object(intake, pdf_factory, monkeypatch):
    from app.modules.resume import service

    c, _ = intake
    _, candidate = c.sessions.start()

    def reject_queue(**kwargs):
        raise RuntimeError("synthetic queue write failure")

    monkeypatch.setattr(service, "WorkQueueRow", reject_queue)
    with pytest.raises(RuntimeError, match="synthetic"):
        service.ResumeService(c).accept(candidate, pdf_factory(), "application/pdf")
    with c.app_sessions() as session:
        assert list(session.scalars(select(ResumeUploadRow))) == []
        assert list(session.scalars(select(AnalysisRunRow))) == []
    assert not any(p.is_file() for p in c.object_store._root.rglob("*"))


def test_new_job_refreshes_uploaded_candidate_without_parsing_again(
    intake, pdf_factory, monkeypatch
):
    from app.modules.matching.scoring import Matcher
    from app.modules.resume import worker as resume_module
    from app.orchestration.worker import MatchWorker
    from tests.jobs.factories import make_event, make_job

    c, client = intake
    accepted = upload(client, pdf_factory([["Skills", "Python, SQL"]])).json()
    resume_worker = ResumeWorker(c)
    matcher = Matcher(c.embedding_client, c.clock)
    match_worker = MatchWorker(c.match_queue, c.match_service(matcher), c.clock, c.dispatcher)
    resume_worker.step()
    match_worker.step()
    resume_worker.finish_matching()
    version = c.profiles.get(accepted["candidate_id"]).profile_version

    def must_not_parse(*args, **kwargs):
        raise AssertionError("Job import must not parse the resume again")

    monkeypatch.setattr(resume_module, "extract_resume", must_not_parse)
    c.jobs.save_with_event(make_job(), make_event())
    assert match_worker.step()
    result = client.get(f"/api/v1/candidates/{accepted['candidate_id']}/recommendations")
    assert result.status_code == 200
    assert result.json()["results"][0]["job_id"] == "job-1"
    assert c.profiles.get(accepted["candidate_id"]).profile_version == version
