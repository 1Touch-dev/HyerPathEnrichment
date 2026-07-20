"""Readiness probe: Postgres + Redis must be reachable."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_ready_returns_200_when_db_and_redis_ok() -> None:
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)

    with patch("app.modules.health.router.get_redis_client", return_value=redis):
        client = TestClient(app)
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ready"


def test_ready_returns_503_when_db_fails() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("app.modules.health.router.SessionLocal", return_value=session_cm):
        client = TestClient(app)
        response = client.get("/ready")

    assert response.status_code == 503
    assert "not ready" in response.json()["error"]["message"]


def test_ready_returns_503_when_schema_behind() -> None:
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)

    with (
        patch("app.modules.health.router.get_redis_client", return_value=redis),
        patch("app.modules.health.router.database_schema_at_head", new_callable=AsyncMock, return_value=False),
    ):
        client = TestClient(app)
        response = client.get("/ready")

    assert response.status_code == 503
    assert "not ready" in response.json()["error"]["message"]


def test_ready_returns_503_when_redis_fails() -> None:
    redis = AsyncMock()
    redis.ping = AsyncMock(side_effect=ConnectionError("redis down"))

    with patch("app.modules.health.router.get_redis_client", return_value=redis):
        client = TestClient(app)
        response = client.get("/ready")

    assert response.status_code == 503
    assert "not ready" in response.json()["error"]["message"]
