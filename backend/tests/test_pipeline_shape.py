import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.workers import runner


class _FakeRedis:
    def __init__(self) -> None:
        self._sets: dict[str, set[str]] = {}

    async def sadd(self, key: str, *values: str) -> int:
        members = self._sets.setdefault(key, set())
        added = len([value for value in values if value not in members])
        members.update(values)
        return added

    async def sismember(self, key: str, value: str) -> bool:
        return value in self._sets.get(key, set())


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    # No live external calls in CI: replace the Redis client used by the
    # orchestrator with an in-memory stand-in.
    fake = _FakeRedis()
    monkeypatch.setattr(runner, "get_redis_client", lambda: fake)


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


def test_opt_out_suppresses_enrichment() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer change-me"}
    identifier = "suppressed-user@example.com"

    response = client.post("/api/opt-out", headers=headers, json={"identifier": identifier, "reason": "gdpr"})
    assert response.status_code == 202

    response = client.get("/api/opt-out/check", headers=headers, params={"identifier": identifier})
    assert response.status_code == 200
    assert response.json()["suppressed"] is True

    response = client.post(
        "/enrich/sync",
        headers=headers,
        json={"email": identifier, "requested_tiers": ["tier2"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "suppressed"
    assert payload["dossier"]["metadata"]["suppressed"] is True
