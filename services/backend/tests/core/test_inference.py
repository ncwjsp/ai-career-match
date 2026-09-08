"""Embedding transport behavior. No AWS account or network access is used."""

import json

import pytest

from app.core.errors import DependencyUnavailable
from app.core.inference import (
    DeterministicEmbeddingClient,
    SageMakerEmbeddingClient,
    build_embedding_client,
)
from app.core.settings import Settings


class FakeRuntime:
    def __init__(self, body=None, fail_with: Exception | None = None):
        self.body = body
        self.fail_with = fail_with
        self.calls: list[dict] = []

    def invoke_endpoint(self, EndpointName, ContentType, Accept, Body):  # noqa: N803
        if self.fail_with:
            raise self.fail_with
        self.calls.append({"endpoint": EndpointName, "payload": json.loads(Body)})
        return {"Body": _Body(json.dumps(self.body).encode("utf-8"))}


class _Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


def response(vectors, dimensions=2, model_id="m", model_revision="r"):
    return {
        "vectors": vectors,
        "dimensions": dimensions,
        "model_id": model_id,
        "model_revision": model_revision,
    }


def test_deterministic_client_is_reproducible_and_unit_length():
    client = DeterministicEmbeddingClient(dimensions=8)
    first = client.embed(["python engineer"])
    second = client.embed(["python engineer"])
    assert first == second
    assert first.dimensions == 8 and len(first.vectors[0]) == 8
    assert abs(sum(v * v for v in first.vectors[0]) - 1.0) < 1e-9
    assert client.embed(["a"]).vectors != client.embed(["b"]).vectors


def test_sagemaker_sends_the_agreed_payload_and_returns_model_identity():
    runtime = FakeRuntime(response([[0.6, 0.8], [1.0, 0.0]]))
    client = SageMakerEmbeddingClient("career-embeddings", client=runtime)
    batch = client.embed(["resume text", "job text"])
    assert runtime.calls[0] == {
        "endpoint": "career-embeddings",
        "payload": {"inputs": ["resume text", "job text"]},
    }
    assert batch.vectors == [[0.6, 0.8], [1.0, 0.0]]
    assert (batch.model_id, batch.model_revision, batch.dimensions) == ("m", "r", 2)


@pytest.mark.parametrize(
    "body",
    [
        response([[0.6, 0.8]], dimensions=3),  # vector shorter than declared
        response([[0.6, 0.8], [1.0, 0.0]]),  # more vectors than inputs
        response([[0.0, 0.0]]),  # zero vector cannot be scored
        response([[float("inf"), 1.0]]),  # non-finite
        response([[0.6, 0.8]], model_revision=""),  # unversioned model
        {"vectors": [[0.6, 0.8]]},  # missing identity fields
        [1, 2, 3],  # not an object
    ],
)
def test_an_unusable_endpoint_response_is_an_outage_not_a_vector(body):
    client = SageMakerEmbeddingClient("career-embeddings", client=FakeRuntime(body))
    with pytest.raises(DependencyUnavailable):
        client.embed(["resume text"])


def test_endpoint_failures_are_retryable():
    client = SageMakerEmbeddingClient(
        "career-embeddings", client=FakeRuntime(fail_with=Exception("throttled"))
    )
    with pytest.raises(DependencyUnavailable) as error:
        client.embed(["resume text"])
    assert error.value.retryable


def test_an_empty_batch_is_a_caller_error():
    client = SageMakerEmbeddingClient("career-embeddings", client=FakeRuntime(response([])))
    with pytest.raises(ValueError, match="at least one"):
        client.embed([])


def test_an_endpoint_name_is_required():
    with pytest.raises(ValueError, match="endpoint name"):
        SageMakerEmbeddingClient("")


def test_the_default_configuration_builds_the_offline_client():
    assert isinstance(build_embedding_client(Settings()), DeterministicEmbeddingClient)
