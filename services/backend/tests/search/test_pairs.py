import pytest

from app.core.errors import DependencyUnavailable
from app.search.pairs import PersistedPairEmbeddings
from app.testing.fixtures import load_fixtures
from tests.nlp.test_embeddings import FixtureEncoder


class Records:
    def __init__(self):
        self.records = {}

    def get(self, entity_id, version, embedding_version):
        return self.records.get((entity_id, version, embedding_version))

    def save(self, record):
        self.records[record.entity_id, record.entity_version, record.embedding_version] = record


def test_persisted_pair_reused_without_inference():
    fixtures = load_fixtures()
    candidates, jobs = Records(), Records()
    service = PersistedPairEmbeddings(FixtureEncoder(), candidates, jobs)
    first = service.embed_pair(fixtures.profiles[0], fixtures.jobs[0])

    class NoInference:
        def embed(self, texts):
            raise AssertionError("Stored vectors must be reused")

    service.client = NoInference()
    assert service.embed_pair(fixtures.profiles[0], fixtures.jobs[0]) == first
    key = next(iter(jobs.records))
    jobs.records[key] = jobs.records[key].model_copy(update={"model_revision": "incompatible"})
    with pytest.raises(DependencyUnavailable):
        service.embed_pair(fixtures.profiles[0], fixtures.jobs[0])
