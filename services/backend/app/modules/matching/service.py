"""Read accessors backing the recommendations API. Owner: M2 (B-06).

Ranking and scoring already happened in the worker (B-10's Matcher plus
C-08's dispatch/publication) before any HTTP request exists; this module only
reads back what was already published and computed, and turns "nothing
published yet" into the API's NotFound rather than a bare `None`.
"""

from __future__ import annotations

from app.contracts.interfaces import RecommendationRepository
from app.contracts.models import RecommendationSet
from app.core.errors import NotFound


class RecommendationReader:
    def __init__(self, recommendations: RecommendationRepository):
        self._recommendations = recommendations

    def latest(self, candidate_id: str) -> RecommendationSet:
        result = self._recommendations.latest(candidate_id)
        if result is None:
            # A valid, authorized candidate can still have no revision yet if
            # the worker has not processed their profile.ready event. The
            # client's own analysis-status poll (A-05) is what tells it when
            # to start calling this endpoint at all.
            raise NotFound("No recommendations have been published for this candidate yet.")
        return result
