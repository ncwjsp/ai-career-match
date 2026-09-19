"""Team-only single URL imports using the existing durable job service."""

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.models import IngestionReport, JobImportRequest
from app.core.access import require_import_access
from app.core.errors import InvalidRequest
from app.modules.jobs.ingest import UnsupportedSourceError

router = APIRouter(
    prefix="/api/v1", tags=["job-imports"], dependencies=[Depends(require_import_access)]
)


@router.post("/job-imports", response_model=IngestionReport)
def import_job(body: JobImportRequest, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return request.app.state.container.job_ingestion.import_url(body.url)
    except UnsupportedSourceError as error:
        raise InvalidRequest(str(error)) from error
