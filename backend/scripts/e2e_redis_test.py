"""End-to-end Redis integration test (Option A — local API + worker + Redis).

Prerequisites:
  - Redis on REDIS_URL (default redis://localhost:6379/0)
  - API on http://localhost:8000
  - RQ worker: python -m app.workers.rq_worker (from backend/)

Usage:
  cd backend
  python scripts/e2e_redis_test.py
"""

from __future__ import annotations

import sys
import time

import httpx
import redis

from app.core.config import get_settings

BASE = "http://localhost:8000"
HEADERS = {"Authorization": f"Bearer {get_settings().api_token}"}


def check_redis() -> None:
    settings = get_settings()
    client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
    if not client.ping():
        raise SystemExit(f"Redis not reachable at {settings.redis_url}")


def check_api() -> None:
    try:
        r = httpx.get(f"{BASE}/health", timeout=5)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise SystemExit(f"API not reachable at {BASE} — start: uvicorn app.main:app --reload --port 8000\n{exc}") from exc


def test_health() -> None:
    r = httpx.get(f"{BASE}/health", timeout=5)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    print("PASS  health")


def test_async_queue() -> None:
    r = httpx.post(
        f"{BASE}/enrich",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"username": "e2e-async-user", "requested_tiers": ["tier2"]},
        timeout=10,
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued", body
    job_id = body["id"]
    print(f"PASS  async enqueue  job_id={job_id}")

    deadline = time.time() + 60
    final = None
    while time.time() < deadline:
        poll = httpx.get(f"{BASE}/enrich/{job_id}", headers=HEADERS, timeout=10)
        assert poll.status_code == 200, poll.text
        final = poll.json()
        if final["status"] not in ("queued", "running"):
            break
        time.sleep(2)

    assert final is not None, "no poll response"
    assert final["status"] == "completed", final
    assert final["dossier"]["handles"], "expected handles in dossier"
    print("PASS  async poll completed")


def test_suppression() -> None:
    identifier = "e2e-blocked@example.com"
    # Opt-out is unauthenticated — no Authorization header.
    r = httpx.post(
        f"{BASE}/api/opt-out",
        headers={"Content-Type": "application/json"},
        json={"identifier": identifier, "reason": "e2e-test"},
        timeout=10,
    )
    assert r.status_code == 202, r.text

    settings = get_settings()
    rds = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    hashes = rds.smembers("suppression:hashes")
    assert hashes, "expected hash in suppression:hashes set"

    check = httpx.get(
        f"{BASE}/api/opt-out/check",
        params={"identifier": identifier},
        timeout=10,
    )
    assert check.json()["suppressed"] is True

    enrich = httpx.post(
        f"{BASE}/enrich/sync",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"email": identifier, "requested_tiers": ["tier2"]},
        timeout=60,
    )
    assert enrich.status_code == 200, enrich.text
    assert enrich.json()["status"] == "suppressed"
    print("PASS  suppression (unauthenticated opt-out + enrich blocked)")


def test_rate_limit() -> None:
    body = {"username": "e2e-rate", "requested_tiers": ["tier2"]}
    codes: list[int] = []
    for _ in range(11):
        r = httpx.post(
            f"{BASE}/enrich/sync",
            headers={**HEADERS, "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        codes.append(r.status_code)
    assert codes[-1] == 429, f"expected 429 on 11th request, got {codes}"
    print("PASS  rate limit (11th request -> 429)")


def main() -> None:
    print("E2E Redis test — checking prerequisites...")
    check_redis()
    check_api()
    print("Running tests...\n")
    test_health()
    test_async_queue()
    test_suppression()
    test_rate_limit()
    print("\nAll E2E checks passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"\nFAIL  {exc}", file=sys.stderr)
        sys.exit(1)
