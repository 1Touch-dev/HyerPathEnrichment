from typing import Any

import pytest
from fastapi.testclient import TestClient

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
from app.main import app
from app.domain.enrichment import EnrichmentRequest
from app.modules.enrichment import service as enrichment_service
from app.enrichers.pipeline import Pipeline
from app.database.session import SessionLocal, init_db


def _stub(fragment: dict[str, Any]):
    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        return dict(fragment)

    return _fetch


@pytest.fixture(autouse=True)
def _offline_enrichers(monkeypatch: pytest.MonkeyPatch) -> None:
    # No live external calls in CI: replace every enricher's backend seam
    # (_fetch) with deterministic offline fragments. The base Enricher.run
    # wrapper still tags sources, so this exercises the real merge + scoring
    # path without shelling out to tools or hitting sidecars.
    monkeypatch.setattr(
        SherlockEnricher,
        "_fetch",
        _stub(
            {
                "handles": [
                    {
                        "platform": "X",
                        "username": "candidate",
                        "profile_url": "https://x.com/candidate",
                        "confidence": 0.75,
                        "metadata": {"provider": "Sherlock", "matched": True},
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        MaigretEnricher,
        "_fetch",
        _stub(
            {
                "handles": [
                    {
                        "platform": "Reddit",
                        "username": "candidate",
                        "profile_url": "https://reddit.com/u/candidate",
                        "confidence": 0.71,
                        "metadata": {"provider": "Maigret", "matched": True},
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        SocialAnalyzerEnricher,
        "_fetch",
        _stub(
            {
                "handles": [
                    {
                        "platform": "Linkedin",
                        "username": "candidate",
                        "profile_url": "https://linkedin.com/in/candidate",
                        "confidence": 0.88,
                        "metadata": {"provider": "Social Analyzer", "matched": True},
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        GitReconEnricher,
        "_fetch",
        _stub(
            {
                "handles": [
                    {
                        "platform": "GitHub",
                        "username": "candidate",
                        "profile_url": "https://github.com/candidate",
                        "confidence": 0.9,
                        "metadata": {"provider": "GitRecon", "matched": True},
                    }
                ],
                "github": {"profile": "https://github.com/candidate", "organizations": [], "public_commits": 12},
                "emails": ["candidate@example.com"],
            }
        ),
    )
    monkeypatch.setattr(TheHarvesterEnricher, "_fetch", _stub({"emails": ["candidate@example.com"]}))
    monkeypatch.setattr(EmailDiscoverEnricher, "_fetch", _stub({"emails": ["candidate@example.com"]}))
    monkeypatch.setattr(
        EmailVerifyEnricher,
        "_fetch",
        _stub(
            {
                "verified_emails": [
                    {"value": "candidate@example.com", "status": "deliverable", "confidence": 0.55, "source": "mx"}
                ]
            }
        ),
    )
    monkeypatch.setattr(CrossLinkedEnricher, "_fetch", _stub({"coworkers": ["Jamie Flores"]}))
    monkeypatch.setattr(
        JobSpyEnricher,
        "_fetch",
        _stub(
            {
                "jobs": [
                    {
                        "title": "Staff Backend Engineer",
                        "company": "Hyrepath Labs",
                        "location": "Remote",
                        "remote": True,
                        "source": "JobSpy",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        LocalBusinessEnricher,
        "_fetch",
        _stub(
            {
                "business": {
                    "name": "Example Business",
                    "address": "123 Market Street",
                    "website": "https://example.com",
                    "rating": 4.7,
                    "phone": "+1 (415) 555-0133",
                    "metadata": {"provider": "Google Maps Scraper"},
                }
            }
        ),
    )
    monkeypatch.setattr(
        LinkedInPhotoEnricher,
        "_fetch",
        _stub(
            {
                "photo": {
                    "source": "linkedin-photo",
                    "asset_url": "https://cdn.example.com/linkedin/candidate.jpg",
                    "captured_at": "2026-07-08T00:00:00+00:00",
                    "confidence": 0.84,
                }
            }
        ),
    )


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_sync_enrich_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        headers={"Authorization": "Bearer change-me"},
        json={
            "email": "alex@hyrepath.dev",
            "linkedin_url": "https://linkedin.com/in/alex-hyrepath",
            "username": "alexhyrepath",
            "company": "Hyrepath",
            "job_search": "Staff Backend Engineer",
            "requested_tiers": ["tier1", "tier2", "tier3", "tier4"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["dossier"]["handles"]
    assert payload["dossier"]["confidence"]
    assert payload["dossier"]["photo"] is None
    assert "pipeline_id" in payload["dossier"]["metadata"]


def test_sync_skips_tier1_photo(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_tier1", True)
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        headers={"Authorization": "Bearer change-me"},
        json={
            "linkedin_url": "https://linkedin.com/in/alex-hyrepath",
            "username": "alex-hyrepath",
            "requested_tiers": ["tier1", "tier2"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["dossier"]["photo"] is None
    assert "linkedin-photo" not in payload["dossier"]["sources"]


def test_opt_out_suppresses_enrichment() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer change-me"}
    identifier = "suppressed-user@example.com"

    response = client.post("/api/opt-out", json={"identifier": identifier, "reason": "gdpr"})
    assert response.status_code == 202

    response = client.get("/api/opt-out/check", params={"identifier": identifier})
    assert response.status_code == 200
    assert response.json()["suppressed"] is True

    response = client.post(
        "/enrich/sync",
        headers=headers,
        json={"email": identifier, "username": "suppressed-user", "requested_tiers": ["tier2"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "suppressed"
    assert payload["dossier"]["metadata"]["suppressed"] is True


def test_sync_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_sync_requests_per_minute", 2)
    client = TestClient(app)
    headers = {"Authorization": "Bearer change-me"}
    body = {"username": "ratelimited", "requested_tiers": ["tier2"]}

    assert client.post("/enrich/sync", headers=headers, json=body).status_code == 200
    assert client.post("/enrich/sync", headers=headers, json=body).status_code == 200
    third = client.post("/enrich/sync", headers=headers, json=body)
    assert third.status_code == 429
    assert third.json()["detail"] == "rate limit exceeded"


def test_async_enrich_enqueues_queued_job(monkeypatch: pytest.MonkeyPatch) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(enrichment_service, "enqueue_enrichment", lambda job_id: enqueued.append(job_id))

    client = TestClient(app)
    response = client.post(
        "/enrich",
        headers={"Authorization": "Bearer change-me"},
        json={"username": "async-user", "requested_tiers": ["tier2"]},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["dossier"]["handles"] == []
    assert enqueued == [payload["id"]]


def test_async_enrich_suppressed_skips_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(enrichment_service, "enqueue_enrichment", lambda job_id: enqueued.append(job_id))

    client = TestClient(app)
    headers = {"Authorization": "Bearer change-me"}
    identifier = "async-suppressed@example.com"

    client.post("/api/opt-out", json={"identifier": identifier, "reason": "gdpr"})

    response = client.post(
        "/enrich",
        headers=headers,
        json={"email": identifier, "username": "suppressed-user", "requested_tiers": ["tier2"]},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "suppressed"
    assert payload["dossier"]["metadata"]["suppressed"] is True
    assert enqueued == []


async def test_execute_job_runs_pipeline() -> None:
    await init_db()
    async with SessionLocal() as session:
        orchestrator = Pipeline(session)
        request = EnrichmentRequest(username="worker-user", requested_tiers=["tier2"])
        job = await orchestrator.create_queued_job(request)
        assert job.status == "queued"

        result = await orchestrator.execute_job(job.id)
        assert result is not None
        assert result.status == "completed"
        assert result.dossier_payload["handles"]


async def test_execute_job_runs_tier1_on_worker_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_tier1", True)
    await init_db()
    async with SessionLocal() as session:
        orchestrator = Pipeline(session)
        request = EnrichmentRequest(
            linkedin_url="https://linkedin.com/in/alex-hyrepath",
            requested_tiers=["tier1"],
        )
        job = await orchestrator.create_queued_job(request)
        result = await orchestrator.execute_job(job.id)
        assert result is not None
        assert result.status == "completed"
        assert result.dossier_payload["photo"] is not None
        assert result.dossier_payload["photo"]["confidence"] == 0.84
