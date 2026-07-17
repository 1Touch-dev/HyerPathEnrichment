"""Pipeline contract tests: partial failure, tier dispatch, validation, suppression."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.enrichers import (
    JobSpyEnricher,
    MaigretEnricher,
    SherlockEnricher,
    SocialAnalyzerEnricher,
)
from app.enrichers.base import Enricher
from app.main import app
from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import RequestedTier
from app.modules.enrichment import service as enrichment_service
from app.enrichers.pipeline import Pipeline
from app.database.session import SessionLocal, init_db

AUTH_HEADERS = {"Authorization": "Bearer change-me"}


def _stub(fragment: dict[str, Any]):
    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        return dict(fragment)

    return _fetch


def _tier_validation_enabled() -> bool:
    try:
        EnrichmentRequest(username="candidate", requested_tiers=[RequestedTier.tier1])
    except ValidationError as exc:
        return any("tier1 requires linkedin_url" in str(error["msg"]) for error in exc.errors())
    return False


@pytest.fixture(autouse=True)
def _offline_enrichers(monkeypatch: pytest.MonkeyPatch) -> None:
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


class _BoomEnricher(Enricher):
    source_name = "Boom"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return True

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        raise RuntimeError("backend down")


@pytest.mark.asyncio
async def test_partial_failure_one_enricher_raises() -> None:
    await init_db()
    async with SessionLocal() as session:
        orchestrator = Pipeline(session)
        orchestrator.tier2 = [SherlockEnricher(), _BoomEnricher(), SocialAnalyzerEnricher()]
        request = EnrichmentRequest(username="pipeline-user", requested_tiers=["tier2"])
        result = await orchestrator.run(request)
        assert result.status == "completed"
        platforms = {handle["platform"] for handle in result.dossier_payload["handles"]}
        assert "X" in platforms
        assert "Linkedin" in platforms


def test_multi_tier_dispatch_respects_selection() -> None:
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        headers=AUTH_HEADERS,
        json={
            "username": "candidate",
            "job_search": "Staff Backend Engineer",
            "requested_tiers": ["tier2", "tier4"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["dossier"]["handles"]
    assert payload["dossier"]["jobs"]
    assert payload["dossier"]["verified_emails"] == []
    assert payload["dossier"]["coworkers"] == []


def test_tier1_skipped_on_sync_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_tier1", True)
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        headers=AUTH_HEADERS,
        json={
            "linkedin_url": "https://linkedin.com/in/candidate",
            "username": "candidate",
            "requested_tiers": ["tier1", "tier2"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["dossier"]["photo"] is None


@pytest.mark.xfail(not _tier_validation_enabled(), reason="requires task 51", strict=False)
def test_invalid_tier1_without_linkedin_422() -> None:
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        headers=AUTH_HEADERS,
        json={"username": "candidate", "requested_tiers": ["tier1"]},
    )
    assert response.status_code == 422
    assert "tier1 requires linkedin_url" in response.text


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        ({"email": "user@example.com", "requested_tiers": ["tier2"]}, "tier2 requires username"),
        (
            {"business": "Acme", "requested_tiers": ["tier3"]},
            "tier3 requires at least one of username, email, or company",
        ),
        (
            {"username": "candidate", "requested_tiers": ["tier4"]},
            "tier4 requires at least one of job_search or business",
        ),
    ],
)
@pytest.mark.xfail(not _tier_validation_enabled(), reason="requires task 51", strict=False)
def test_tier_validation_rules(payload: dict[str, Any], expected_message: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        EnrichmentRequest(**payload)
    assert expected_message in str(exc_info.value.errors()[0]["msg"])


def test_suppressed_async_and_sync() -> None:
    client = TestClient(app)
    identifier = "contracts-suppressed@example.com"

    client.post("/api/opt-out", json={"identifier": identifier, "reason": "gdpr"})

    async_resp = client.post(
        "/enrich",
        headers=AUTH_HEADERS,
        json={"email": identifier, "username": "ignored", "requested_tiers": ["tier2"]},
    )
    assert async_resp.status_code == 202
    assert async_resp.json()["status"] == "suppressed"

    sync_resp = client.post(
        "/enrich/sync",
        headers=AUTH_HEADERS,
        json={"email": identifier, "username": "ignored", "requested_tiers": ["tier2"]},
    )
    assert sync_resp.status_code == 200
    assert sync_resp.json()["status"] == "suppressed"


def test_async_enrich_suppressed_skips_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(enrichment_service, "enqueue_enrichment", lambda job_id: enqueued.append(job_id))

    client = TestClient(app)
    identifier = "contracts-async-skip@example.com"
    client.post("/api/opt-out", json={"identifier": identifier, "reason": "gdpr"})

    response = client.post(
        "/enrich",
        headers=AUTH_HEADERS,
        json={"email": identifier, "username": "ignored", "requested_tiers": ["tier2"]},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "suppressed"
    assert enqueued == []
