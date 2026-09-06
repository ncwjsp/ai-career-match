from fastapi import FastAPI

from app.core.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    if config.app_env == "production":
        raise RuntimeError("Production is not supported by the bootstrap.")
    application = FastAPI(title="AI Career Match API", version="0.1.0")
    application.state.settings = config

    @application.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready", tags=["health"])
    def ready() -> dict[str, str]:
        return {"status": "ok", "mode": "mock", "dependencies": "not_required"}

    return application


app = create_app()
