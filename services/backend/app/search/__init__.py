"""Job-vector search. Owner: M2 (B-03).

Stored vectors plus exact cosine retrieval, not OpenSearch or another
external search cluster -- the 2026-09-08 scope revision keeps OpenSearch out
of the MVP (see plan.md/START_HERE.md); career_jobs stays a manually-imported,
small corpus, and its vectors live in `career_jobs` alongside the postings
they describe (B-09).
"""

from app.search.rebuild import rebuild_job_embeddings
from app.search.retrieval import JobVectorSearch, SearchHit

__all__ = ["JobVectorSearch", "SearchHit", "rebuild_job_embeddings"]
