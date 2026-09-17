import math

import pytest

from app.contracts.models import EvidenceRef, ProcessedText
from app.core.errors import DependencyUnavailable
from app.core.inference import EmbeddingBatch
from app.nlp.embeddings import (
    DIMENSIONS,
    EMBEDDING_VERSION,
    MODEL_ID,
    MODEL_REVISION,
    VersionedEmbedder,
)


class FixtureEncoder:
    """Deliberately synthetic vectors with the expected identity for contract tests only."""

    def embed(self, texts):
        self.inputs = texts
        return EmbeddingBatch(
            [[1.0] + [0.0] * (DIMENSIONS - 1) for _ in texts], MODEL_ID, MODEL_REVISION, DIMENSIONS
        )


def source(identity="resume-1", text="Python\r\nengineering"):
    return ProcessedText(
        text=text,
        language="en",
        preprocessing_version="raw",
        evidence=[
            EvidenceRef(
                document_id=identity,
                document_version=1,
                chunk_id="text",
                start=0,
                end=len(text),
                excerpt=text,
            )
        ],
    )


def test_candidate_and_job_share_normalization_and_model():
    client = FixtureEncoder()
    records = VersionedEmbedder(client).encode([source(), source("job-1")], EMBEDDING_VERSION)
    assert records[0].vector == records[1].vector
    assert records[0].entity_id == "resume-1"
    assert records[1].entity_id == "job-1"
    assert records[0].preprocessing_version == "shared-text-v1"
    assert all(math.isfinite(n) for n in records[0].vector)


def test_candidate_identity_can_differ_from_resume_evidence():
    record = VersionedEmbedder(FixtureEncoder()).encode_entity(source(), "candidate-1", 2)
    assert (record.entity_id, record.entity_version) == ("candidate-1", 2)


def test_reject_model_drift_and_hash_mock():
    from app.core.inference import DeterministicEmbeddingClient

    with pytest.raises(DependencyUnavailable):
        VersionedEmbedder(DeterministicEmbeddingClient()).encode([source()], EMBEDDING_VERSION)


def test_empty_and_unknown_versions():
    embedder = VersionedEmbedder(FixtureEncoder())
    assert embedder.encode([], EMBEDDING_VERSION) == []
    with pytest.raises(ValueError):
        embedder.encode([source()], "future-version")
    with pytest.raises(ValueError):
        embedder.encode([source().model_copy(update={"evidence": []})], EMBEDDING_VERSION)


def test_direct_matching_transport_rejects_model_drift_and_batches():
    from app.core.inference import DeterministicEmbeddingClient
    from app.nlp.embeddings import BaselineEmbeddingClient

    with pytest.raises(DependencyUnavailable):
        BaselineEmbeddingClient(DeterministicEmbeddingClient()).embed(["Python"])

    class Bounded(FixtureEncoder):
        def embed(self, texts):
            assert len(texts) <= 32
            return super().embed(texts)

    assert len(BaselineEmbeddingClient(Bounded()).embed(["Python"] * 65).vectors) == 65
    assert len(VersionedEmbedder(Bounded()).encode([source()] * 65, EMBEDDING_VERSION)) == 65


@pytest.mark.parametrize("language", [None, "th"])
def test_language_is_explicit(language):
    with pytest.raises(ValueError):
        VersionedEmbedder(FixtureEncoder()).encode(
            [source().model_copy(update={"language": language})], EMBEDDING_VERSION
        )
