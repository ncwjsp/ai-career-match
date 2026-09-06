"""Public v1 contracts. Every handler remains explicitly unimplemented."""

from typing import Annotated, NoReturn

from fastapi import APIRouter, File, UploadFile

from app.contracts.models import (
    AnalysisRun,
    CandidateProfile,
    ErrorResponse,
    JobPosting,
    MatchExplanation,
    RecommendationSet,
    UploadAccepted,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["planned"],
    responses={
        501: {"model": ErrorResponse, "description": "Planned feature; not implemented."},
        422: {"model": ErrorResponse, "description": "Invalid request."},
    },
)


class PlannedFeatureError(Exception):
    pass


def not_implemented() -> NoReturn:
    raise PlannedFeatureError()


@router.post("/resumes", response_model=UploadAccepted, status_code=202)
async def upload_resume(file: Annotated[UploadFile, File()]):
    # Do not retain or parse uploaded data in the bootstrap.
    await file.close()
    not_implemented()


@router.get("/analyses/{analysis_id}", response_model=AnalysisRun)
def analysis_status(analysis_id: str):
    not_implemented()


@router.get("/resumes/{resume_id}/profile", response_model=CandidateProfile)
def candidate_profile(resume_id: str):
    not_implemented()


@router.get("/candidates/{candidate_id}/recommendations", response_model=RecommendationSet)
def candidate_recommendations(candidate_id: str):
    not_implemented()


@router.get("/jobs/{job_id}", response_model=JobPosting)
def job_detail(job_id: str):
    not_implemented()


EXPLANATION_PATH = "/candidates/{candidate_id}/recommendations/{revision}/jobs/{job_id}/explanation"


@router.post(EXPLANATION_PATH, response_model=MatchExplanation, status_code=202)
def request_explanation(candidate_id: str, revision: int, job_id: str):
    not_implemented()


@router.get(EXPLANATION_PATH, response_model=MatchExplanation)
def explanation_status(candidate_id: str, revision: int, job_id: str):
    not_implemented()
