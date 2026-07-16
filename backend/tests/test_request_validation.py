"""Tier-specific EnrichmentRequest validation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models import EnrichmentRequest, RequestedTier

AUTH_HEADERS = {"Authorization": "Bearer change-me"}


def _validation_message(exc: ValidationError) -> str:
    return str(exc.errors()[0]["msg"])


class TestEnrichmentRequestTierValidation:
    def test_default_tiers_require_all_identifiers(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            EnrichmentRequest(email="user@example.com")
        message = _validation_message(exc_info.value)
        assert "tier1 requires linkedin_url" in message

    def test_empty_requested_tiers_validates_all_tier_rules(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            EnrichmentRequest(username="jane", requested_tiers=[])
        message = _validation_message(exc_info.value)
        assert "tier1 requires linkedin_url" in message

    def test_tier1_requires_linkedin_url(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            EnrichmentRequest(username="jane", requested_tiers=[RequestedTier.tier1])
        assert "tier1 requires linkedin_url" in _validation_message(exc_info.value)

    def test_tier1_accepts_linkedin_url(self) -> None:
        request = EnrichmentRequest(
            linkedin_url="https://linkedin.com/in/jane",
            requested_tiers=[RequestedTier.tier1],
        )
        assert request.linkedin_url == "https://linkedin.com/in/jane"

    def test_tier2_requires_username(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            EnrichmentRequest(email="user@example.com", requested_tiers=[RequestedTier.tier2])
        assert "tier2 requires username" in _validation_message(exc_info.value)

    def test_tier2_accepts_username(self) -> None:
        request = EnrichmentRequest(username="jane", requested_tiers=[RequestedTier.tier2])
        assert request.username == "jane"

    def test_tier3_requires_username_email_or_company(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            EnrichmentRequest(business="Acme", requested_tiers=[RequestedTier.tier3])
        assert "tier3 requires at least one of username, email, or company" in _validation_message(
            exc_info.value
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"username": "jane", "requested_tiers": [RequestedTier.tier3]},
            {"email": "jane@example.com", "requested_tiers": [RequestedTier.tier3]},
            {"company": "Acme", "requested_tiers": [RequestedTier.tier3]},
        ],
    )
    def test_tier3_accepts_required_identifiers(self, payload: dict) -> None:
        request = EnrichmentRequest(**payload)
        assert RequestedTier.tier3 in request.requested_tiers

    def test_tier4_requires_job_search_or_business(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            EnrichmentRequest(username="jane", requested_tiers=[RequestedTier.tier4])
        assert "tier4 requires at least one of job_search or business" in _validation_message(
            exc_info.value
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"job_search": "SRE", "requested_tiers": [RequestedTier.tier4]},
            {"business": "Coffee Shop", "requested_tiers": [RequestedTier.tier4]},
        ],
    )
    def test_tier4_accepts_required_identifiers(self, payload: dict) -> None:
        request = EnrichmentRequest(**payload)
        assert RequestedTier.tier4 in request.requested_tiers

    def test_all_tiers_valid_with_full_payload(self) -> None:
        request = EnrichmentRequest(
            linkedin_url="https://linkedin.com/in/jane",
            username="jane",
            email="jane@example.com",
            company="Acme",
            job_search="Engineer",
            business="Acme HQ",
        )
        assert set(request.requested_tiers) == set(RequestedTier)


class TestEnrichSyncTierValidation:
    def test_sync_rejects_tier2_without_username(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/enrich/sync",
            headers=AUTH_HEADERS,
            json={"email": "user@example.com", "requested_tiers": ["tier2"]},
        )
        assert response.status_code == 422
        assert "tier2 requires username" in response.text

    def test_sync_rejects_tier1_without_linkedin_url(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/enrich/sync",
            headers=AUTH_HEADERS,
            json={"username": "jane", "requested_tiers": ["tier1"]},
        )
        assert response.status_code == 422
        assert "tier1 requires linkedin_url" in response.text

    def test_sync_rejects_tier3_without_required_identifiers(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/enrich/sync",
            headers=AUTH_HEADERS,
            json={"business": "Acme", "requested_tiers": ["tier3"]},
        )
        assert response.status_code == 422
        assert "tier3 requires at least one of username, email, or company" in response.text

    def test_sync_rejects_tier4_without_required_identifiers(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/enrich/sync",
            headers=AUTH_HEADERS,
            json={"username": "jane", "requested_tiers": ["tier4"]},
        )
        assert response.status_code == 422
        assert "tier4 requires at least one of job_search or business" in response.text

    def test_sync_accepts_valid_tier2_request(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/enrich/sync",
            headers=AUTH_HEADERS,
            json={"username": "jane", "requested_tiers": ["tier2"]},
        )
        assert response.status_code == 200
