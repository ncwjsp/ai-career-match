from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.planned import PlannedFeatureError
from app.api.router import router
from app.contracts.models import ErrorDetail, ErrorResponse
from app.core.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    if config.app_env == "production":
        raise RuntimeError("Production is not supported by the bootstrap.")
    application = FastAPI(
        title="AI Career Match API",
        version="0.1.0",
        description=(
            "Shared bootstrap. /api/v1 handlers return 501 until their owners implement them. "
            "/dev/fixtures returns synthetic data only; production mode is disabled."
        ),
    )
    application.state.settings = config
    application.include_router(router)

    def error_response(code: str, message: str, status: int):
        body = ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                retryable=False,
                request_id=str(uuid4()),
            )
        )
        return JSONResponse(status_code=status, content=body.model_dump(mode="json"))

    @application.exception_handler(PlannedFeatureError)
    async def planned_error(request: Request, exc: PlannedFeatureError):
        return error_response(
            "NOT_IMPLEMENTED", "This feature is planned but not implemented.", 501
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error_response(
            "INVALID_REQUEST", "The request does not match the API contract.", 422
        )

    @application.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready", tags=["health"])
    def ready() -> dict[str, str]:
        return {"status": "ok", "mode": "mock", "dependencies": "not_required"}

    return application


app = create_app()
