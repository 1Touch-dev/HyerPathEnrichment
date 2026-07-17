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


def _stub(fragment: dict[str, Any]):
    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        return dict(fragment)

    return _fetch


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
    monkeypatch.setattr(MaigretEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(SocialAnalyzerEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(GitReconEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(TheHarvesterEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(EmailDiscoverEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(EmailVerifyEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(CrossLinkedEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(JobSpyEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(LocalBusinessEnricher, "_fetch", _stub({}))
    monkeypatch.setattr(LinkedInPhotoEnricher, "_fetch", _stub({}))


def _create_sync_job(client: TestClient, headers: dict[str, str], email: str) -> str:
    response = client.post(
        "/enrich/sync",
        headers=headers,
        json={"email": email, "username": email.split("@")[0], "requested_tiers": ["tier2"]},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_list_jobs_pagination() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer change-me"}

    _create_sync_job(client, headers, "first@example.com")
    _create_sync_job(client, headers, "second@example.com")
    _create_sync_job(client, headers, "third@example.com")

    page_one = client.get("/enrich?limit=2&offset=0", headers=headers)
    assert page_one.status_code == 200
    payload = page_one.json()
    assert payload["total"] >= 3
    assert payload["limit"] == 2
    assert payload["offset"] == 0
    assert len(payload["jobs"]) == 2

    page_two = client.get("/enrich?limit=2&offset=2", headers=headers)
    assert page_two.status_code == 200
    payload_two = page_two.json()
    assert payload_two["limit"] == 2
    assert payload_two["offset"] == 2
    assert len(payload_two["jobs"]) >= 1

    page_one_ids = {job["id"] for job in page_one.json()["jobs"]}
    page_two_ids = {job["id"] for job in payload_two["jobs"]}
    assert page_one_ids.isdisjoint(page_two_ids)

    for job in page_one.json()["jobs"]:
        assert "id" in job
        assert "status" in job
        assert "created_at" in job
        assert "updated_at" in job
        assert "request_payload" in job
        assert "identifier_summary" in job
        assert job["request_payload"].get("email", "") in job["identifier_summary"]


def test_list_jobs_requires_bearer() -> None:
    client = TestClient(app)
    response = client.get("/enrich")
    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized"
