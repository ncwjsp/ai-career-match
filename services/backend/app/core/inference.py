"""Embedding transport. Owner: M3 (C-01/C-06 infrastructure).

The 2026-09-08 revision hosts NLP/embedding inference on a SageMaker endpoint.
This module owns only the *transport*: it turns text into vectors and reports
which model produced them. M1 keeps the `Embedder` port (A-04) and wraps one of
these clients to build `EmbeddingRecord`s with entity ids and versions; M3 does
not implement resume or job semantics here.

The request/response contract below is the agreed serialization for D04. M1's
A-07 packaging must serve it, and A-07 parity is checked by running the same
texts through `DeterministicEmbeddingClient`'s real counterpart locally and
through the endpoint.

    request   {"inputs": ["text", ...]}
    response  {"vectors": [[...], ...], "model_id": "...",
               "model_revision": "...", "dimensions": 384}

`dimensions` is verified against every returned vector, because a silently
changed endpoint would otherwise corrupt stored vectors and every score
computed from them.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.core.errors import DependencyUnavailable
from app.core.settings import Settings


@dataclass(frozen=True)
class EmbeddingBatch:
    """Vectors plus the model identity that must be persisted alongside them."""

    vectors: list[list[float]]
    model_id: str
    model_revision: str
    dimensions: int


class EmbeddingClient(Protocol):
    def embed(self, texts: Sequence[str]) -> EmbeddingBatch: ...


class DeterministicEmbeddingClient:
    """Offline stand-in: a hashed unit vector per text.

    It is reproducible and dimension-correct, which is all the queue, storage
    and revision tests need. It carries **no semantics** and must never be used
    to produce a reported match score; real mode refuses this backend.
    """

    model_id = "deterministic-hash"
    model_revision = "local-1"

    def __init__(self, dimensions: int = 16):
        if dimensions < 1:
            raise ValueError("An embedding needs at least one dimension.")
        self._dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            vectors=[self._vector(text) for text in texts],
            model_id=self.model_id,
            model_revision=self.model_revision,
            dimensions=self._dimensions,
        )

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [digest[i % len(digest)] - 127.5 for i in range(self._dimensions)]
        norm = math.sqrt(sum(value * value for value in raw))
        if norm == 0:  # pragma: no cover - sha256 cannot produce a zero vector
            raw[0], norm = 1.0, 1.0
        return [value / norm for value in raw]


class SageMakerEmbeddingClient:
    """Invokes one SageMaker endpoint. `client` is injected so tests are offline."""

    def __init__(
        self,
        endpoint_name: str,
        client=None,
        region: str | None = None,
        timeout_seconds: int = 30,
    ):
        if not endpoint_name:
            raise ValueError("SageMakerEmbeddingClient requires an endpoint name.")
        self._endpoint = endpoint_name
        self._client = client
        self._region = region
        self._timeout = timeout_seconds

    @property
    def client(self):
        if self._client is None:
            self._client = _build_runtime_client(self._region, self._timeout)
        return self._client

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        if not texts:
            raise ValueError("An embedding request needs at least one text.")
        payload = json.dumps({"inputs": list(texts)}).encode("utf-8")
        try:
            response = self.client.invoke_endpoint(
                EndpointName=self._endpoint,
                ContentType="application/json",
                Accept="application/json",
                Body=payload,
            )
            body = json.loads(response["Body"].read())
        except Exception as error:  # noqa: BLE001 - any endpoint failure is an outage
            raise DependencyUnavailable("The embedding endpoint is unavailable.") from error
        return _parse(body, len(texts))


def _parse(body: object, expected_count: int) -> EmbeddingBatch:
    if not isinstance(body, dict):
        raise DependencyUnavailable("The embedding endpoint returned an unexpected body.")
    vectors = body.get("vectors")
    dimensions = body.get("dimensions")
    model_id = body.get("model_id")
    model_revision = body.get("model_revision")
    if (
        not isinstance(vectors, list)
        or len(vectors) != expected_count
        or not isinstance(dimensions, int)
        or not isinstance(model_id, str)
        or not isinstance(model_revision, str)
        or not model_id
        or not model_revision
    ):
        raise DependencyUnavailable("The embedding endpoint returned an incomplete response.")
    parsed: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, list) or len(vector) != dimensions:
            raise DependencyUnavailable(
                "The embedding endpoint returned a vector of the wrong dimension."
            )
        values = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in values) or not any(values):
            raise DependencyUnavailable(
                "The embedding endpoint returned a zero or non-finite vector."
            )
        parsed.append(values)
    return EmbeddingBatch(parsed, model_id, model_revision, dimensions)


def _build_runtime_client(region: str | None, timeout_seconds: int):
    try:
        import boto3
        from botocore.config import Config
    except ModuleNotFoundError as error:  # pragma: no cover - boto3 is pinned
        raise DependencyUnavailable("boto3 is required for SageMaker inference.") from error
    return boto3.client(
        "sagemaker-runtime",
        region_name=region,
        config=Config(
            read_timeout=timeout_seconds,
            connect_timeout=min(timeout_seconds, 10),
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def build_embedding_client(settings: Settings) -> EmbeddingClient:
    """Build the client the configuration asks for. Called once at startup."""
    if settings.embedding_backend == "local":
        return DeterministicEmbeddingClient()
    return SageMakerEmbeddingClient(
        endpoint_name=settings.sagemaker_embedding_endpoint,
        client=_build_runtime_client(
            settings.sagemaker_region_or_default, settings.sagemaker_timeout_seconds
        ),
        region=settings.sagemaker_region_or_default,
        timeout_seconds=settings.sagemaker_timeout_seconds,
    )
