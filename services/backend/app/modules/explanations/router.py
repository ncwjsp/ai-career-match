"""Explanation endpoints. Owner: M3 (C-02/C-05).

Both routes are candidate-scoped: the session cookie decides which candidate's
data may be read, so one visitor cannot fetch another's explanation by guessing
an id. An explanation is always requested for a specific published revision, so
the prose a reader sees belongs to the ranking they are looking at.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.contracts.models import ErrorResponse, MatchExplanation, Recommendation
from app.core.access import candidate_scope
from app.core.errors import NotFound

router = APIRouter(
    prefix="/api/v1",
    tags=["explanations"],
    responses={
        403: {"model": ErrorResponse, "description": "Not this session's candidate."},
        404: {"model": ErrorResponse, "description": "Unknown revision or job."},
    },
)

PATH = "/candidates/{candidate_id}/recommendations/{revision}/jobs/{job_id}/explanation"


@router.post(PATH, response_model=MatchExplanation, status_code=202)
def request_explanation(
    request: Request, candidate_id: str, revision: int, job_id: str
) -> MatchExplanation:
    """Generate (or return the cached) explanation for one ranked job."""
    candidate_scope(request, candidate_id)
    container = request.app.state.container
    recommendation = _entry(container, candidate_id, revision, job_id)
    profile = container.profiles.get(candidate_id, recommendation.profile_version)
    job = container.jobs.get(job_id, recommendation.job_version)
    if profile is None or job is None:
        raise NotFound("The ranked profile or job version is no longer available.")
    return container.explanations.explain(profile, job, recommendation)


@router.get(PATH, response_model=MatchExplanation)
def explanation_status(
    request: Request, response: Response, candidate_id: str, revision: int, job_id: str
) -> MatchExplanation:
    """Read a generated explanation without triggering generation."""
    candidate_scope(request, candidate_id)
    container = request.app.state.container
    cached = container.explanations.cached(candidate_id, revision, job_id)
    if cached is not None:
        return cached
    recommendation = _entry(container, candidate_id, revision, job_id)
    response.status_code = 202
    return MatchExplanation(
        candidate_id=candidate_id,
        revision=revision,
        profile_version=recommendation.profile_version,
        job_id=job_id,
        job_version=recommendation.job_version,
        scoring_version=recommendation.scoring_version,
        state="pending",
        text=None,
        # The evidence-backed parts are available before any generation runs.
        strengths=list(recommendation.strengths),
        gaps=list(recommendation.gaps),
        evidence=list(recommendation.evidence),
        model_version=None,
        prompt_version=None,
        generated_at=None,
    )


def _entry(container, candidate_id: str, revision: int, job_id: str) -> Recommendation:
    published = container.recommendations.get(candidate_id, revision)
    if published is None:
        raise NotFound("Unknown recommendation revision.")
    for entry in published.results:
        if entry.job_id == job_id:
            return entry
    raise NotFound("That job is not in this revision.")
