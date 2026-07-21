"""API tests for the `/enrich/{job_id}/events` SSE route."""

from __future__ import annotations

import pytest

from app.database.session import SessionLocal, init_db
from app.domain.enrichment import EnrichmentRequest
from app.enrichers.pipeline import Pipeline
from app.main import app
from fastapi.testclient import TestClient

_HEADERS = {"Authorization": "Bearer change-me"}


async def _create_completed_job() -> str:
    await init_db()
    async with SessionLocal() as session:
        pipeline = Pipeline(session)
        request = EnrichmentRequest(username="sse-user", requested_tiers=["tier2"])
        job = await pipeline.create_queued_job(request)
        result = await pipeline.execute_job(job.id)
        assert result is not None
        return result.id


async def test_events_route_returns_completed_status_for_finished_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.enrichers import (
        CrossLinkedEnricher,
        EmailDiscoverEnricher,
        EmailVerifyEnricher,
        GitReconEnricher,
        JobSpyEnricher,
        LinkedInPhotoEnricher,
        LocalBusinessEnricher,
        MaigretEnricher,
        SherlockEnricher,
        SocialAnalyzerEnricher,
        TheHarvesterEnricher,
    )

    async def _empty_fetch(self, request: EnrichmentRequest) -> dict:
        return {}

    for enricher in (
        SherlockEnricher,
        MaigretEnricher,
        EmailDiscoverEnricher,
        EmailVerifyEnricher,
        GitReconEnricher,
        JobSpyEnricher,
        LinkedInPhotoEnricher,
        LocalBusinessEnricher,
        SocialAnalyzerEnricher,
        TheHarvesterEnricher,
        CrossLinkedEnricher,
    ):
        monkeypatch.setattr(enricher, "_fetch", _empty_fetch)
    monkeypatch.setattr(get_settings(), "enable_tier1", False)

    job_id = await _create_completed_job()

    client = TestClient(app)
    response = client.get(f"/enrich/{job_id}/events", headers=_HEADERS)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert f'"job_id": "{job_id}"' in response.text
    assert '"status": "completed"' in response.text


def test_events_route_returns_404_for_unknown_job() -> None:
    client = TestClient(app)
    response = client.get("/enrich/does-not-exist/events", headers=_HEADERS)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_events_route_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/enrich/does-not-exist/events")

    assert response.status_code == 401
