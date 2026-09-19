"""Versioned persisted vectors shared by both matching trigger directions."""

from app.contracts.models import EmbeddingRecord
from app.core.errors import DependencyUnavailable
from app.core.inference import EmbeddingBatch
from app.modules.matching.text import job_text, profile_text
from app.nlp.embeddings import DIMENSIONS, EMBEDDING_VERSION, MODEL_ID, MODEL_REVISION
from app.nlp.types import PREPROCESSING_VERSION


class PersistedPairEmbeddings:
    def __init__(self, client, candidates, jobs):
        self.client, self.candidates, self.jobs = client, candidates, jobs

    def _get(self, repository, entity_id, version, text):
        record = repository.get(entity_id, version, EMBEDDING_VERSION)
        if record is None:
            batch = self.client.embed([text])
            if len(batch.vectors) != 1:
                raise DependencyUnavailable("The embedding service returned an invalid batch.")
            record = EmbeddingRecord(
                entity_id=entity_id,
                entity_version=version,
                vector=batch.vectors[0],
                model_id=batch.model_id,
                model_revision=batch.model_revision,
                dimensions=batch.dimensions,
                preprocessing_version=PREPROCESSING_VERSION,
                embedding_version=EMBEDDING_VERSION,
            )
            self._validate(record)
            repository.save(record)
        self._validate(record)
        return record.vector

    @staticmethod
    def _validate(record):
        if (
            record.model_id,
            record.model_revision,
            record.dimensions,
            record.preprocessing_version,
            record.embedding_version,
        ) != (MODEL_ID, MODEL_REVISION, DIMENSIONS, PREPROCESSING_VERSION, EMBEDDING_VERSION):
            raise DependencyUnavailable(
                "Stored embeddings do not match the selected model version."
            )

    def embed_pair(self, profile, job):
        candidate = self._get(
            self.candidates, profile.candidate_id, profile.profile_version, profile_text(profile)
        )
        posting = self._get(self.jobs, job.job_id, job.content_version, job_text(job))
        return EmbeddingBatch([candidate, posting], MODEL_ID, MODEL_REVISION, DIMENSIONS)
