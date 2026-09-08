"""Public v1 contracts still owned by M1/M2. Each handler is explicitly
unimplemented: uploads and the profile read belong to A-05, and the jobs and
recommendations reads belong to B-06. M3 implements the explanation routes in
app/modules/explanations/router.py."""

from typing import Annotated, NoReturn

from fastapi import APIRouter, File, UploadFile

from app.contracts.models import (
    AnalysisRun,
    CandidateProfile,
    ErrorResponse,
    JobPosting,
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


# The explanation routes are implemented in app/modules/explanations/router.py.
