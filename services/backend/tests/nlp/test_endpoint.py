import io
import json
import os

import pytest
from fastapi.testclient import TestClient

from app.core.inference import SageMakerEmbeddingClient
from app.core.settings import Settings
from app.nlp.endpoint import create_endpoint
from app.nlp.processor import SharedTextProcessor
from app.nlp.remote import SageMakerNlpProcessor
from tests.nlp.test_embeddings import FixtureEncoder, source


class EndpointTransport:
    """Exercise the real endpoint HTTP schema without making an AWS call."""

    def __init__(self, client):
        self.client = client

    def invoke_endpoint(self, **kwargs):
        result = self.client.post("/invocations", content=kwargs["Body"])
        result.raise_for_status()
        return {"Body": io.BytesIO(result.content)}


def test_nlp_and_embedding_serialization_parity():
    with TestClient(create_endpoint(FixtureEncoder())) as client:
        assert client.get("/ping").status_code == 200
        transport = EndpointTransport(client)
        remote = SageMakerNlpProcessor(
            Settings(sagemaker_embedding_endpoint="synthetic"), transport
        )
        text = source(text="Skills\nPython and SQL. No Java experience.")
        assert remote.analyze(text) == SharedTextProcessor("resume-1", 1).analyze(text)
        batch = SageMakerEmbeddingClient("synthetic", transport).embed(["Python"])
        assert batch == FixtureEncoder().embed(["Python"])
        for payload in [[], {"inputs": [None]}, {"task": "nlp", "source": {}}]:
            assert client.post("/invocations", json=payload).status_code == 422
        assert client.post("/invocations", content="x" * (4 * 1024 * 1024 + 1)).status_code == 413


def test_artifact_rejects_missing_files_and_tampering(tmp_path):
    from app.nlp.cpu_embedding import verify_artifact
    from app.nlp.embeddings import MODEL_ID, MODEL_REVISION

    (tmp_path / "artifact.json").write_text(
        json.dumps(
            {
                "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "sha256": {},
            }
        )
    )
    with pytest.raises(ValueError, match="checksum manifest"):
        verify_artifact(tmp_path)


@pytest.mark.skipif(not os.environ.get("ACM_MODEL_DIR"), reason="Opt-in real pinned CPU artifact")
def test_real_cpu_endpoint_parity_and_long_document_tail():
    from app.nlp.cpu_embedding import CpuEmbeddingClient
    from app.nlp.embeddings import DIMENSIONS

    encoder = CpuEmbeddingClient(os.environ["ACM_MODEL_DIR"])
    texts = ["Python developer", "Python engineer", "Cooking food", "Python " * 700 + "SQL " * 300]
    local = encoder.embed(texts)
    with TestClient(create_endpoint(encoder)) as client:
        remote = SageMakerEmbeddingClient("local-http-test", EndpointTransport(client)).embed(texts)
    for left, right in zip(local.vectors, remote.vectors, strict=True):
        assert len(left) == DIMENSIONS
        assert left == pytest.approx(right, abs=1e-6)
        assert sum(n * n for n in left) == pytest.approx(1, abs=1e-5)

    def similarity(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert similarity(local.vectors[0], local.vectors[1]) > similarity(
        local.vectors[0], local.vectors[2]
    )
    assert encoder.embed(["Python " * 700]).vectors[0] != pytest.approx(local.vectors[3])
    assert encoder.embed([texts[0]]).vectors[0] == pytest.approx(local.vectors[0], abs=1e-5)
