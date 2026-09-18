"""Real row-lock checks; opt in with ACM_TEST_POSTGRES_URL on a test database."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select

from app.core.container import Container
from app.core.errors import ConflictError
from app.core.settings import Settings
from app.core.storage import LocalObjectStore
from app.db.app.models import AnalysisRunRow, ResumeUploadRow, WorkQueueRow
from app.db.app.queue import SqlWorkQueue
from app.modules.resume.service import ResumeService

pytestmark = pytest.mark.skipif(
    not os.environ.get("ACM_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_concurrent_uploads_accept_exactly_one(app_session_factory, clock, tmp_path, pdf_factory):
    c = Container(Settings(app_env="test"), clock)
    c.__dict__.update(
        app_sessions=app_session_factory, object_store=LocalObjectStore(tmp_path / "objects")
    )
    _, candidate = c.sessions.start()
    data = pdf_factory()
    barrier = Barrier(2)

    def upload():
        barrier.wait(timeout=10)
        try:
            ResumeService(c).accept(candidate, data, "application/pdf")
            return "accepted"
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: upload(), range(2)))
    assert sorted(results) == ["accepted", "conflict"]
    with app_session_factory() as session:
        for model in (AnalysisRunRow, ResumeUploadRow, WorkQueueRow):
            assert len(list(session.scalars(select(model)))) == 1
    assert len([p for p in (tmp_path / "objects").rglob("*") if p.is_file()]) == 1


def test_workers_skip_locked_work_and_claim_once(app_session_factory, clock):
    queue = SqlWorkQueue(app_session_factory, clock, "analysis")
    for index in range(9):
        queue.enqueue_payload(f"work-{index}", "synthetic", {})
    barrier = Barrier(8)

    def claim(index):
        barrier.wait(timeout=10)
        return queue.claim_payload(f"worker-{index}")[0]

    # Hold the first row locked throughout all claims: other workers must skip it.
    with app_session_factory() as holder, holder.begin():
        holder.scalar(
            select(WorkQueueRow).where(WorkQueueRow.event_id == "work-0").with_for_update()
        )
        with ThreadPoolExecutor(max_workers=8) as pool:
            claimed = list(pool.map(claim, range(8)))
        assert set(claimed) == {f"work-{i}" for i in range(1, 9)}
    assert queue.claim_payload("last")[0] == "work-0"
    assert queue.claim_payload("extra") is None


def test_reclaimed_lease_rejects_previous_owner(app_session_factory, clock):
    queue = SqlWorkQueue(app_session_factory, clock, "analysis", lease_seconds=10)
    queue.enqueue_payload("lease-test", "synthetic", {})
    assert queue.claim_payload("old")
    clock.advance(11)
    assert queue.claim_payload("new")
    assert not queue.renew("lease-test", "old")
    queue.acknowledge("lease-test", "old")
    queue.retry("lease-test", "stale failure", "old")
    with app_session_factory() as session:
        row = session.get(WorkQueueRow, "lease-test")
        assert (row.state, row.lease_owner, row.attempts) == ("inflight", "new", 2)
    assert queue.renew("lease-test", "new")
    queue.acknowledge("lease-test", "new")
    assert queue.counts() == {"done": 1}
