from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.planned import PlannedFeatureError
from app.api.router import router
from app.contracts.models import ErrorDetail, ErrorResponse
from app.core.container import Container
from app.core.errors import AppError
from app.core.settings import Settings


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    config = settings or Settings()
    config.validate_for_runtime()
    application = FastAPI(
        title="AI Career Match API",
        version="0.1.0",
        description=(
            "Shared bootstrap. /api/v1 handlers return 501 until their owners implement them. "
            "/dev/fixtures returns synthetic data only; production mode is disabled."
        ),
    )
    application.state.settings = config
    application.state.container = container or Container(settings=config)
    application.include_router(router)

    def error_response(code: str, message: str, status: int, retryable: bool = False):
        body = ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                retryable=retryable,
                request_id=str(uuid4()),
            )
        )
        return JSONResponse(status_code=status, content=body.model_dump(mode="json"))

    @application.exception_handler(PlannedFeatureError)
    async def planned_error(request: Request, exc: PlannedFeatureError):
        return error_response(
            "NOT_IMPLEMENTED", "This feature is planned but not implemented.", 501
        )

    @application.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        # Domain code raises AppError; only this handler builds the wire body.
        return error_response(exc.code, exc.message, exc.status, exc.retryable)

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
        # Mock mode deliberately reports that no external dependency is needed;
        # real mode names the adapters a deployment must actually reach.
        if config.app_mode == "mock":
            return {"status": "ok", "mode": "mock", "dependencies": "not_required"}
        return {
            "status": "ok",
            "mode": "real",
            "dependencies": f"postgresql,{config.object_store_backend},{config.embedding_backend}",
        }

    return application


app = create_app()
