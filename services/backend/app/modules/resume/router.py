"""A-05 bounded upload and session-scoped analysis/profile reads."""

from typing import Annotated

from fastapi import APIRouter, File, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.contracts.models import AnalysisRun, CandidateProfile, ErrorResponse, UploadAccepted
from app.core.access import session_token, set_session_cookie
from app.core.errors import Forbidden, InvalidRequest, NotFound, PayloadTooLarge
from app.modules.resume.errors import ResumeExtractionError
from app.modules.resume.service import ResumeService
from app.modules.resume.types import MEDIA_TYPES, ExtractionLimits
from app.modules.resume.validation import validate_upload

router = APIRouter(
    prefix="/api/v1",
    tags=["resume"],
    responses={code: {"model": ErrorResponse} for code in [403, 404, 409, 413, 422, 503]},
)


@router.post("/resumes", response_model=UploadAccepted, status_code=202)
async def upload_resume(request: Request, response: Response, file: Annotated[UploadFile, File()]):
    c = request.app.state.container
    try:
        data = await file.read(c.settings.max_upload_bytes + 1)
        if len(data) > c.settings.max_upload_bytes:
            raise PayloadTooLarge()
        try:
            kind = await run_in_threadpool(
                validate_upload,
                data,
                file.filename or "",
                file.content_type,
                ExtractionLimits(max_file_bytes=c.settings.max_upload_bytes),
            )
        except ResumeExtractionError as error:
            mapped = InvalidRequest(str(error))
            mapped.code = error.code.value
            raise mapped from error
    finally:
        await file.close()
    token = session_token(request)
    candidate = await run_in_threadpool(c.sessions.resolve, token)
    if candidate is None:
        token, candidate = await run_in_threadpool(c.sessions.start)
    result = await run_in_threadpool(ResumeService(c).accept, candidate, data, MEDIA_TYPES[kind])
    expiry = await run_in_threadpool(c.sessions.expires_at, token)
    set_session_cookie(
        response, token, c.settings, max(0, int((expiry - c.clock.now()).total_seconds()))
    )
    response.headers["Cache-Control"] = "no-store"
    return result


def _candidate(request):
    candidate = request.app.state.container.sessions.resolve(session_token(request))
    if candidate is None:
        raise Forbidden("A valid candidate session is required.")
    return candidate


@router.get("/analyses/{analysis_id}", response_model=AnalysisRun)
def analysis_status(request: Request, response: Response, analysis_id: str):
    candidate = _candidate(request)
    run = request.app.state.container.analyses.get(analysis_id)
    if run is None or run.candidate_id != candidate:
        raise NotFound("No analysis is available in this session.")
    response.headers["Cache-Control"] = "no-store"
    return run


@router.get("/resumes/{resume_id}/profile", response_model=CandidateProfile)
def candidate_profile(request: Request, response: Response, resume_id: str):
    candidate = _candidate(request)
    response.headers["Cache-Control"] = "no-store"
    return ResumeService(request.app.state.container).profile(candidate, resume_id)
