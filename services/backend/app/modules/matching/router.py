"""Recommendations read route. Owner: M2 (B-06).

Candidate-scoped the same way C-02's explanation route is: only the session
that owns this candidate may read their ranked recommendations
(`app.core.access.candidate_scope`). Not yet mounted -- `app/api/router.py`
(M3's) still serves the planned 501 stub at this same path
(`app/api/planned.py::candidate_recommendations`); wiring this router in ahead
of that stub and removing the stub handler is M3's step, exactly as it did for
the explanation routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.models import ErrorResponse, RecommendationSet
from app.core.access import candidate_scope
from app.modules.matching.service import RecommendationReader

router = APIRouter(
    prefix="/api/v1",
    tags=["matching"],
    responses={
        403: {"model": ErrorResponse, "description": "Not this session's candidate."},
        404: {"model": ErrorResponse, "description": "No published recommendations yet."},
    },
)


@router.get("/candidates/{candidate_id}/recommendations", response_model=RecommendationSet)
def candidate_recommendations(request: Request, candidate_id: str) -> RecommendationSet:
    candidate_scope(request, candidate_id)
    container = request.app.state.container
    return RecommendationReader(container.recommendations).latest(candidate_id)
