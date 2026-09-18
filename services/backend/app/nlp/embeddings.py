"""A-04 versioned records over the shared local/SageMaker embedding transport."""

from collections.abc import Sequence

from pydantic import ValidationError

from app.contracts.models import EmbeddingRecord, ProcessedText
from app.core.errors import DependencyUnavailable
from app.core.inference import EmbeddingBatch, EmbeddingClient
from app.nlp.text import normalize_text
from app.nlp.types import PREPROCESSING_VERSION

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DIMENSIONS = 384
EMBEDDING_VERSION = "minilm-1110a243-shared-v1-token254-mean-v1"


class BaselineEmbeddingClient:
    """Apply the same normalization/version gate to M2's direct transport calls."""

    def __init__(self, client: EmbeddingClient):
        self.client = client

    def embed(self, texts):
        if not texts:
            raise ValueError("Provide at least one text.")
        vectors = []
        for start in range(0, len(texts), 32):
            inputs = [normalize_text(text).text for text in texts[start : start + 32]]
            if any(not text or len(text) > 200_000 for text in inputs):
                raise ValueError("Embedding input exceeds the baseline text limits.")
            batch = self.client.embed(inputs)
            if (batch.model_id, batch.model_revision, batch.dimensions) != (
                MODEL_ID,
                MODEL_REVISION,
                DIMENSIONS,
            ) or len(batch.vectors) != len(inputs):
                raise DependencyUnavailable("The embedding endpoint changed model identity.")
            vectors.extend(batch.vectors)
        return EmbeddingBatch(vectors, MODEL_ID, MODEL_REVISION, DIMENSIONS)


class VersionedEmbedder:
    """Evidence supplies identity for the unchanged Embedder protocol.

    Call encode_entity when the persisted entity is a candidate rather than the
    source resume. Both entry points apply identical normalization/version checks.
    The model client owns token-based chunking so local and remote agree exactly.
    """

    def __init__(self, client: EmbeddingClient):
        self.client = client

    def encode(self, texts: Sequence[ProcessedText], version: str) -> list[EmbeddingRecord]:
        identities = []
        for source in texts:
            ids = {(e.document_id, e.document_version) for e in source.evidence}
            if len(ids) != 1:
                raise ValueError("Embedding sources require one unambiguous evidence identity.")
            identities.append(next(iter(ids)))
        return self._encode(texts, identities, version)

    def encode_entity(self, source: ProcessedText, entity_id: str, entity_version: int):
        return self._encode([source], [(entity_id, entity_version)], EMBEDDING_VERSION)[0]

    def _encode(self, texts, identities, version):
        if version != EMBEDDING_VERSION:
            raise ValueError("Unknown embedding version; rebuild vectors explicitly.")
        if not texts:
            return []
        if len(texts) > 32:
            return [
                record
                for start in range(0, len(texts), 32)
                for record in self._encode(
                    texts[start : start + 32], identities[start : start + 32], version
                )
            ]
        normalized = []
        for source in texts:
            if source.language not in {"en", "en-us", "en-gb"}:
                raise ValueError("The baseline embedding supports declared English only.")
            text = normalize_text(source.text).text
            if not text or len(text) > 200_000:
                raise ValueError("Embedding input must contain 1-200000 normalized characters.")
            normalized.append(text)
        batch = self.client.embed(normalized)
        if (batch.model_id, batch.model_revision, batch.dimensions) != (
            MODEL_ID,
            MODEL_REVISION,
            DIMENSIONS,
        ) or len(batch.vectors) != len(texts):
            raise DependencyUnavailable(
                "Embedding model identity differs from the pinned baseline."
            )
        try:
            return [
                EmbeddingRecord(
                    entity_id=identity[0],
                    entity_version=identity[1],
                    vector=vector,
                    model_id=batch.model_id,
                    model_revision=batch.model_revision,
                    dimensions=batch.dimensions,
                    preprocessing_version=PREPROCESSING_VERSION,
                    embedding_version=version,
                )
                for identity, vector in zip(identities, batch.vectors, strict=True)
            ]
        except ValidationError as error:
            raise DependencyUnavailable(
                "The endpoint returned an invalid embedding vector."
            ) from error
