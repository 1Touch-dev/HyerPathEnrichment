"""Tests for Sentry-compatible central error tracking."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.main import app
from app.observability import error_tracking
from tests.envelope_helpers import assert_error, assert_success


def _reset_error_tracking_state() -> None:
    error_tracking._initialized = False


@pytest.fixture(autouse=True)
def _clear_error_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_error_tracking_state()
    monkeypatch.setattr(get_settings(), "sentry_dsn", "")
    monkeypatch.setattr(get_settings(), "enable_error_tracking_probe", False)


def test_init_error_tracking_no_dsn_is_noop() -> None:
    with patch("sentry_sdk.init") as mock_init:
        error_tracking.init_error_tracking(Settings(sentry_dsn=""))
    mock_init.assert_not_called()
    assert error_tracking.is_enabled() is False


def test_init_error_tracking_sets_environment_and_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "sentry_dsn",
        "http://example@test.local/1",
    )
    monkeypatch.setattr(get_settings(), "sentry_environment", "staging")
    monkeypatch.setattr(get_settings(), "sentry_release", "abc123")
    monkeypatch.setattr(get_settings(), "sentry_traces_sample_rate", 0.0)
    with patch("sentry_sdk.init") as mock_init:
        error_tracking.init_error_tracking()
    mock_init.assert_called_once()
    kwargs = mock_init.call_args.kwargs
    assert kwargs["environment"] == "staging"
    assert kwargs["release"] == "abc123"
    assert kwargs["traces_sample_rate"] == 0.0
    assert kwargs["send_default_pii"] is False


def test_unhandled_exception_captures_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "sentry_dsn", "http://example@test.local/1")
    capture = MagicMock()
    monkeypatch.setattr("app.core.exception_handlers.capture_exception", capture)

    router = APIRouter(route_class=EnvelopeAPIRoute)

    @router.get("/_test/boom")
    async def boom() -> dict:
        raise RuntimeError("secret boom details")

    app.include_router(router)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        body = assert_error(client.get("/_test/boom"), 500, "INTERNAL_ERROR")
        assert body["error"]["message"] == "An unexpected error occurred."
        assert "secret boom details" not in str(body)
        capture.assert_called_once()
        exc = capture.call_args.args[0]
        assert isinstance(exc, RuntimeError)
    finally:
        app.routes[:] = [
            route for route in app.routes if getattr(route, "path", None) != "/_test/boom"
        ]


def test_app_error_does_not_capture(
    monkeypatch: pytest.MonkeyPatch, staff_auth_headers: dict[str, str]
) -> None:
    monkeypatch.setattr(get_settings(), "sentry_dsn", "http://example@test.local/1")
    capture = MagicMock()
    monkeypatch.setattr("app.core.exception_handlers.capture_exception", capture)

    client = TestClient(app)
    assert_error(
        client.get(
            "/enrich/missing-job-id",
            headers=staff_auth_headers,
        ),
        404,
        "NOT_FOUND",
    )
    capture.assert_not_called()


def test_worker_path_captures_and_reraises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "sentry_dsn", "http://example@test.local/1")
    capture = MagicMock()
    set_context = MagicMock()
    monkeypatch.setattr("app.workers.tasks.enrichment.capture_exception", capture)
    monkeypatch.setattr("app.workers.tasks.enrichment.set_job_context", set_context)

    boom = RuntimeError("worker boom")
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(side_effect=boom)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.workers.tasks.enrichment.SessionLocal", return_value=session_cm),
        patch("app.workers.tasks.enrichment.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.enrichment.engine") as mock_engine,
    ):
        mock_engine.dispose = AsyncMock()
        from app.workers.tasks.enrichment import run_enrichment_job

        with pytest.raises(RuntimeError, match="worker boom"):
            run_enrichment_job("job-123")

    set_context.assert_called_once_with("job-123")
    capture.assert_called_once()
    assert capture.call_args.kwargs["tags"] == {"job_id": "job-123"}


def test_error_tracking_probe_disabled_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    assert_error(client.post("/internal/error-tracking-probe"), 404, "NOT_FOUND")


def test_error_tracking_probe_captures_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "enable_error_tracking_probe", True)
    monkeypatch.setattr(get_settings(), "sentry_dsn", "http://example@test.local/1")
    capture = MagicMock()
    flush = MagicMock()
    monkeypatch.setattr("app.modules.health.router.capture_exception", capture)
    monkeypatch.setattr("app.modules.health.router.flush_error_tracking", flush)

    client = TestClient(app)
    data = assert_success(client.post("/internal/error-tracking-probe"))
    assert data["status"] == "captured"
    capture.assert_called_once()
    exc = capture.call_args.args[0]
    assert isinstance(exc, RuntimeError)
    assert capture.call_args.kwargs["tags"] == {"probe": "e2e"}
    flush.assert_called_once()
