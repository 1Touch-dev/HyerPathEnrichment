"""Contract tests for shared success/error API envelopes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_route import EnvelopeAPIRoute
from app.core.errors import NotFoundError
from app.core.responses import success_envelope
from app.enrichers import MaigretEnricher, SherlockEnricher, SocialAnalyzerEnricher
from app.main import app
from tests.envelope_helpers import assert_error, assert_success


def test_health_success_envelope() -> None:
    client = TestClient(app)
    data = assert_success(client.get("/health"))
    assert data["status"] == "ok"
    assert "service" in data


def test_unauthorized_error_envelope() -> None:
    client = TestClient(app)
    body = assert_error(client.get("/enrich"), 401, "UNAUTHORIZED")
    assert body["error"]["message"] == "Invalid or missing authorization"
    assert body["meta"] is None


def test_not_found_error_envelope(staff_auth_headers: dict[str, str]) -> None:
    client = TestClient(app)
    body = assert_error(
        client.get("/enrich/missing-job-id", headers=staff_auth_headers),
        404,
        "NOT_FOUND",
    )
    assert body["error"]["message"] == "job not found"
    assert body["meta"] == {"job_id": "missing-job-id"}


def test_validation_error_envelope(staff_auth_headers: dict[str, str]) -> None:
    client = TestClient(app)
    body = assert_error(
        client.post("/enrich/sync", headers=staff_auth_headers, json={}),
        422,
        "VALIDATION_ERROR",
    )
    assert body["error"]["details"] is not None
    assert isinstance(body["error"]["details"], list)


async def test_rate_limit_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
    db: AsyncSession,
    staff_auth_headers: dict[str, str],
) -> None:
    from app.core.config import get_settings
    from app.modules.enrichment.models import JobRecord

    # Stub tier2 enrichers so this stays a fast, offline test like the rest of
    # the suite (see tests/test_pipeline_shape.py's _offline_enrichers), rather
    # than shelling out to sherlock/maigret/social-analyzer CLIs that aren't
    # installed here and would otherwise time out on each of the 3 calls below.
    async def _fast_fetch(self, request):
        return {}

    monkeypatch.setattr(SherlockEnricher, "_fetch", _fast_fetch)
    monkeypatch.setattr(MaigretEnricher, "_fetch", _fast_fetch)
    monkeypatch.setattr(SocialAnalyzerEnricher, "_fetch", _fast_fetch)

    monkeypatch.setattr(get_settings(), "max_sync_requests_per_minute", 2)
    client = TestClient(app)
    body_payload = {"username": "envelope-rate", "requested_tiers": ["tier2"]}

    created_job_ids: list[str] = []
    try:
        for _ in range(2):
            data = assert_success(
                client.post("/enrich/sync", headers=staff_auth_headers, json=body_payload)
            )
            created_job_ids.append(data["id"])
        body = assert_error(
            client.post("/enrich/sync", headers=staff_auth_headers, json=body_payload),
            429,
            "RATE_LIMIT_EXCEEDED",
        )
        assert body["error"]["message"] == "rate limit exceeded"
        assert body["meta"] is not None
        assert body["meta"]["limit_per_minute"] == 2
    finally:
        # /enrich/sync commits real JobRecord rows via its own session (not the `db`
        # fixture's), so they'd otherwise leak into the shared test DB and pollute
        # other tests that assert on absolute job counts/totals (e.g.
        # test_child_job_visibility.py).
        for job_id in created_job_ids:
            job = await db.get(JobRecord, job_id)
            if job is not None:
                await db.delete(job)
        await db.commit()


def test_ready_error_envelope() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("app.modules.health.router.SessionLocal", return_value=session_cm):
        client = TestClient(app)
        body = assert_error(client.get("/ready"), 503, "SERVICE_UNAVAILABLE")
    assert "not ready" in body["error"]["message"]
    assert body["meta"] == {"reason": "RuntimeError"}


def test_envelope_does_not_double_wrap() -> None:
    router = APIRouter(route_class=EnvelopeAPIRoute)

    @router.get("/_test/already-wrapped")
    async def already_wrapped() -> dict:
        return success_envelope({"ok": True})

    app.include_router(router)
    try:
        client = TestClient(app)
        response = client.get("/_test/already-wrapped")
        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["data"] == {"ok": True}
        assert "success" not in body["data"]
    finally:
        app.routes[:] = [
            route
            for route in app.routes
            if getattr(route, "path", None) != "/_test/already-wrapped"
        ]


def test_unhandled_exception_envelope() -> None:
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
    finally:
        app.routes[:] = [
            route for route in app.routes if getattr(route, "path", None) != "/_test/boom"
        ]


def test_not_found_error_class_meta() -> None:
    err = NotFoundError("missing", meta={"id": "x"})
    assert err.code == "NOT_FOUND"
    assert err.meta == {"id": "x"}
