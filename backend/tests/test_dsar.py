"""DSAR API tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_dsar_access_returns_summary_without_dossier_pii() -> None:
    client = TestClient(app)
    enrich_headers = {"Authorization": "Bearer change-me"}
    identifier = f"dsar-access-{uuid4().hex}@example.com"

    client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "dsar-user", "requested_tiers": ["tier2"]},
    )

    # DSAR is public — no Authorization header.
    response = client.post(
        "/api/dsar",
        json={"identifier": identifier, "request_type": "access"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["request_type"] == "access"
    assert payload["summary"]["job_count"] >= 1
    assert "dossier" not in payload["summary"]

    fetched = client.get(f"/api/dsar/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == payload["id"]


def test_dsar_deletion_suppresses_and_purges() -> None:
    client = TestClient(app)
    enrich_headers = {"Authorization": "Bearer change-me"}
    identifier = f"dsar-delete-{uuid4().hex}@example.com"

    enrich = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "dsar-user", "requested_tiers": ["tier2"]},
    )
    job_id = enrich.json()["id"]

    response = client.post(
        "/api/dsar",
        json={"identifier": identifier, "request_type": "deletion"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["summary"]["suppressed"] is True
    assert payload["summary"]["jobs_cleared"] >= 1

    job = client.get(f"/enrich/{job_id}", headers=enrich_headers)
    assert job.json()["dossier"] == {} or job.json()["status"] == "purged"

    blocked = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "dsar-user", "requested_tiers": ["tier2"]},
    )
    assert blocked.json()["status"] == "suppressed"
