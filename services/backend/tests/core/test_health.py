from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


def test_health_requires_no_database_or_cloud():
    with TestClient(create_app(Settings(app_env="test"))) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json()["mode"] == "mock"


def test_production_cannot_silently_use_mock_mode():
    import pytest

    with pytest.raises(RuntimeError, match="Production"):
        create_app(Settings(app_env="production"))
