"""Retained profiles, upload metadata and vectors."""

from datetime import timedelta

import pytest

from app.contracts.models import FileRef
from app.core.errors import ConflictError, NotFound
from app.db.app.profiles import (
    ProfileVersionConflict,
    SqlCandidateEmbeddingRepository,
    SqlProfileRepository,
    SqlResumeUploadRepository,
)
from app.db.app.sessions import SqlSessionStore
from tests.app.conftest import NOW
from tests.app.factories import make_embedding, make_profile


@pytest.fixture
def store(app_session_factory, clock):
    return SqlSessionStore(app_session_factory, clock, retention_days=30)


@pytest.fixture
def profiles(app_session_factory, clock):
    return SqlProfileRepository(app_session_factory, clock)


@pytest.fixture
def candidate(store):
    _, candidate_id = store.start()
    return candidate_id


def test_a_saved_profile_reads_back_as_the_same_contract(profiles, candidate):
    saved = make_profile(candidate)
    profiles.save(saved)
    loaded = profiles.get(candidate)
    assert loaded is not None
    assert (loaded.candidate_id, loaded.profile_version) == (candidate, 1)
    assert [s.name for s in loaded.skills] == ["Python"]
    assert loaded.summary == saved.summary


def test_get_returns_the_current_version_and_older_ones_on_request(profiles, candidate):
    profiles.save(make_profile(candidate, 1, summary="first"))
    profiles.save(make_profile(candidate, 2, summary="second"))
    assert profiles.get(candidate).profile_version == 2
    assert profiles.get(candidate, version=1).summary == "first"


def test_resaving_a_version_is_a_no_op_but_changing_it_is_a_conflict(profiles, candidate):
    profiles.save(make_profile(candidate, 1, summary="first"))
    profiles.save(make_profile(candidate, 1, summary="first"))
    with pytest.raises(ProfileVersionConflict):
        profiles.save(make_profile(candidate, 1, summary="rewritten"))


def test_a_profile_needs_an_existing_candidate(profiles):
    with pytest.raises(NotFound):
        profiles.save(make_profile("cand-unknown"))


def test_retention_lives_on_the_candidate_not_the_stored_payload(profiles, candidate):
    # The payload claims matching is enabled; disabling it must win immediately.
    profiles.save(make_profile(candidate, matching_enabled=True))
    profiles.set_matching_enabled(candidate, False)
    assert profiles.get(candidate).matching_enabled is False
    assert profiles.list_active(NOW) == []
    assert profiles.is_active(candidate, NOW) is False


def test_expiry_removes_a_candidate_from_matching(profiles, candidate):
    profiles.save(make_profile(candidate))
    assert [p.candidate_id for p in profiles.list_active(NOW)] == [candidate]
    later = NOW + timedelta(days=31)
    assert profiles.list_active(later) == []
    assert profiles.is_active(candidate, later) is False


def test_a_candidate_without_a_profile_is_not_matchable(profiles, candidate):
    assert profiles.list_active(NOW) == []
    assert profiles.get(candidate) is None


def test_list_active_pages_by_id_for_checkpointing(app_session_factory, clock, store):
    profiles = SqlProfileRepository(app_session_factory, clock)
    ids = sorted(store.start()[1] for _ in range(3))
    for candidate_id in ids:
        profiles.save(make_profile(candidate_id))
    first = profiles.list_active(NOW, limit=2)
    assert [p.candidate_id for p in first] == ids[:2]
    second = profiles.list_active(NOW, limit=2, after_id=first[-1].candidate_id)
    assert [p.candidate_id for p in second] == ids[2:]


def test_upload_metadata_stores_the_key_not_the_bytes(app_session_factory, clock, candidate):
    uploads = SqlResumeUploadRepository(app_session_factory, clock)
    file = FileRef(object_key="resumes/resume-abc", media_type="application/pdf")
    uploads.record("resume-1", candidate, file, byte_size=2048, original_filename="cv.pdf")
    assert uploads.file_for("resume-1") == file
    assert uploads.list_for_candidate(candidate) == [file]
    uploads.mark_deleted("resume-1")
    assert uploads.file_for("resume-1") is None
    assert uploads.list_for_candidate(candidate) == []


def test_a_stored_vector_cannot_change_under_the_same_version(
    app_session_factory, clock, profiles, candidate
):
    embeddings = SqlCandidateEmbeddingRepository(app_session_factory, clock)
    profiles.save(make_profile(candidate))
    record = make_embedding(candidate)
    embeddings.save(record)
    embeddings.save(record)
    assert embeddings.get(candidate, 1, "emb-v1") == record
    with pytest.raises(ConflictError):
        embeddings.save(make_embedding(candidate, vector=[1.0, 0.0]))


def test_a_new_embedding_version_stores_a_separate_vector(
    app_session_factory, clock, profiles, candidate
):
    embeddings = SqlCandidateEmbeddingRepository(app_session_factory, clock)
    profiles.save(make_profile(candidate))
    embeddings.save(make_embedding(candidate))
    embeddings.save(make_embedding(candidate, vector=[1.0, 0.0], embedding_version="emb-v2"))
    assert embeddings.get(candidate, 1, "emb-v1").vector == [0.6, 0.8]
    assert embeddings.get(candidate, 1, "emb-v2").vector == [1.0, 0.0]
