import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import EnrichmentRequest
from app.routes import enrich as enrich_route
from app.routes import rate_limit
from app.services import get_orchestrator
from app.storage.db import SessionLocal, init_db
from app.workers import runner


class _FakeRedis:
    def __init__(self) -> None:
        self._sets: dict[str, set[str]] = {}
        self._counters: dict[str, int] = {}

    async def sadd(self, key: str, *values: str) -> int:
        members = self._sets.setdefault(key, set())
        added = len([value for value in values if value not in members])
        members.update(values)
        return added

    async def sismember(self, key: str, value: str) -> bool:
        return value in self._sets.get(key, set())

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return key in self._counters


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    # No live external calls in CI: replace the Redis client used by the
    # orchestrator and rate limiter with a single shared in-memory stand-in.
    fake = _FakeRedis()
    monkeypatch.setattr(runner, "get_redis_client", lambda: fake)
    monkeypatch.setattr(rate_limit, "get_redis_client", lambda: fake)
    return fake


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


def test_sync_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

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
    monkeypatch.setattr(enrich_route, "enqueue_enrichment", lambda job_id: enqueued.append(job_id))

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


async def test_execute_job_runs_pipeline() -> None:
    await init_db()
    async with SessionLocal() as session:
        orchestrator = get_orchestrator(session)
        request = EnrichmentRequest(username="worker-user", requested_tiers=["tier2"])
        job = await orchestrator.create_queued_job(request)
        assert job.status == "queued"

        result = await orchestrator.execute_job(job.id)
        assert result is not None
        assert result.status == "completed"
        assert result.dossier_payload["handles"]
