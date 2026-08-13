"""DSAR API tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer change-me", "X-Test-User-ID": str(uuid4())}


def test_dsar_access_returns_full_enriched_data() -> None:
    """Test that DSAR access returns complete enriched data."""
    client = TestClient(app)
    enrich_headers = _auth_headers()
    identifier = f"dsar-access-{uuid4().hex}@example.com"

    enrich_response = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "dsar-user", "requested_tiers": ["tier2"]},
    )
    assert enrich_response.status_code == 200
    assert enrich_response.json()["data"]["status"] in ["completed", "completed_no_data"]

    response = client.post(
        "/api/dsar",
        headers=enrich_headers,
        json={"identifier": identifier, "request_type": "access"},
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["status"] == "completed"
    assert payload["request_type"] == "access"

    summary = payload["summary"]
    assert summary["job_count"] >= 1
    assert summary["identifier_provided"] == identifier
    assert "enriched_data" in summary
    assert summary["first_job_at"] is not None
    assert summary["last_job_at"] is not None

    fetched = client.get(f"/api/dsar/{payload['id']}", headers=enrich_headers)
    assert fetched.status_code == 200
    assert fetched.json()["data"]["id"] == payload["id"]


def test_dsar_deletion_suppresses_and_purges() -> None:
    client = TestClient(app)
    enrich_headers = _auth_headers()
    identifier = f"dsar-delete-{uuid4().hex}@example.com"

    enrich = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "dsar-user", "requested_tiers": ["tier2"]},
    )
    assert enrich.status_code == 200
    job_id = enrich.json()["data"]["id"]

    response = client.post(
        "/api/dsar",
        headers=enrich_headers,
        json={"identifier": identifier, "request_type": "deletion"},
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["status"] == "completed"
    assert payload["summary"]["suppressed"] is True
    assert payload["summary"]["jobs_cleared"] >= 1

    job = client.get(f"/enrich/{job_id}", headers=enrich_headers)
    job_data = job.json()["data"]
    assert job_data["dossier"] == {} or job_data["status"] == "purged"

    blocked = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "dsar-user", "requested_tiers": ["tier2"]},
    )
    assert blocked.json()["data"]["status"] == "suppressed"


def test_dsar_access_merges_multiple_jobs() -> None:
    """Test that DSAR access merges data from multiple enrichment jobs."""
    client = TestClient(app)
    enrich_headers = _auth_headers()
    identifier = f"dsar-merge-{uuid4().hex}@example.com"

    enrich1 = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "user1", "requested_tiers": ["tier2"]},
    )
    assert enrich1.status_code == 200

    enrich2 = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "user2", "requested_tiers": ["tier2"]},
    )
    assert enrich2.status_code == 200

    response = client.post(
        "/api/dsar",
        headers=enrich_headers,
        json={"identifier": identifier, "request_type": "access"},
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    summary = payload["summary"]

    assert summary["job_count"] >= 2
    assert summary["identifier_provided"] == identifier
    assert "enriched_data" in summary


def test_dsar_access_with_no_jobs() -> None:
    """Test DSAR access for identifier with no enrichment history."""
    client = TestClient(app)
    identifier = f"dsar-nojobs-{uuid4().hex}@example.com"

    response = client.post(
        "/api/dsar",
        headers=_auth_headers(),
        json={"identifier": identifier, "request_type": "access"},
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    summary = payload["summary"]

    assert summary["job_count"] == 0
    assert summary["identifier_provided"] == identifier
    assert summary["enriched_data"] is None
    assert summary["first_job_at"] is None
    assert summary["last_job_at"] is None
