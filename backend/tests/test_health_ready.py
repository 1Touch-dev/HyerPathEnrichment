"""Readiness probe: Postgres + Redis must be reachable."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_ready_returns_200_when_db_and_redis_ok() -> None:
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_returns_503_when_db_fails() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("app.routes.health.SessionLocal", return_value=session_cm):
        client = TestClient(app)
        response = client.get("/ready")

    assert response.status_code == 503
    assert "not ready" in response.json()["detail"]


def test_ready_returns_503_when_redis_fails() -> None:
    redis = AsyncMock()
    redis.ping = AsyncMock(side_effect=ConnectionError("redis down"))

    with patch("app.routes.health.get_redis_client", return_value=redis):
        client = TestClient(app)
        response = client.get("/ready")

    assert response.status_code == 503
    assert "not ready" in response.json()["detail"]
