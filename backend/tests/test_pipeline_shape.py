from fastapi.testclient import TestClient

from app.main import app


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
    assert "pipeline_id" in payload["dossier"]["metadata"]
