"""Job detail read route. Owner: M2 (B-06).

Public: a `JobPosting` is not candidate-specific data, so this route does not
go through `candidate_scope` -- there is no candidate in the path to scope it
to. Not yet mounted -- see `app/modules/matching/router.py` for the mounting
note; the same applies here against `app/api/planned.py::job_detail`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.models import ErrorResponse, JobPosting
from app.core.errors import NotFound

router = APIRouter(
    prefix="/api/v1",
    tags=["jobs"],
    responses={404: {"model": ErrorResponse, "description": "Unknown job."}},
)


@router.get("/jobs/{job_id}", response_model=JobPosting)
def job_detail(request: Request, job_id: str) -> JobPosting:
    container = request.app.state.container
    job = container.jobs.get(job_id)
    if job is None:
        raise NotFound("Unknown job.")
    return job
