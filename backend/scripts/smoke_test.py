"""Short deterministic smoke checks against a running API.

Env:
  BASE_URL          — API root (default http://localhost:8000)
  API_TOKEN         — Bearer token (default change-me)
  SMOKE_TIMEOUT     — per-request timeout seconds (default 60)
  SMOKE_SKIP_ASYNC  — set to 1 to skip async enrich + poll (sync-only)
  SMOKE_PROD        — when set to 1, require explicit BASE_URL (production mode)

Exits non-zero on any failure.
"""

from __future__ import annotations

import os
import sys
import time
import uuid

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.environ.get("API_TOKEN", "change-me")
TIMEOUT = float(os.environ.get("SMOKE_TIMEOUT", "60"))
SKIP_ASYNC = os.environ.get("SMOKE_SKIP_ASYNC", "").strip().lower() in {"1", "true", "yes"}
POLL_INTERVAL = 2.0
POLL_DEADLINE = float(os.environ.get("SMOKE_ASYNC_DEADLINE", "60"))
SMOKE_PROD = os.environ.get("SMOKE_PROD", "").strip() in {"1", "true", "yes"}


def fail(msg: str) -> None:
    print(f"FAIL  {msg}", file=sys.stderr)
    raise SystemExit(1)


def ok(msg: str) -> None:
    print(f"PASS  {msg}")


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def unwrap_success(body: object, label: str) -> dict:
    if not isinstance(body, dict) or body.get("success") is not True or "data" not in body:
        fail(f"{label} expected success envelope, got: {body}")
    data = body["data"]
    if not isinstance(data, dict):
        fail(f"{label} expected object data, got: {body}")
    return data


def main() -> None:
    if SMOKE_PROD and BASE_URL in {"http://localhost:8000", "http://127.0.0.1:8000"}:
        fail("SMOKE_PROD=1 requires BASE_URL pointing at production/staging host")

    # 1. Liveness
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.RequestException as exc:
        fail(f"/health unreachable: {exc}")
    if health.status_code != 200:
        fail(f"/health expected 200, got {health.status_code}")
    body = unwrap_success(health.json(), "/health")
    if body.get("status") != "ok":
        fail(f"/health unexpected data: {body}")
    ok("/health")

    # 2. Readiness (Postgres + Redis)
    try:
        ready = requests.get(f"{BASE_URL}/ready", timeout=10)
    except requests.RequestException as exc:
        fail(f"/ready unreachable: {exc}")
    if ready.status_code != 200:
        fail(f"/ready expected 200, got {ready.status_code}: {ready.text[:200]}")
    ready_body = unwrap_success(ready.json(), "/ready")
    if ready_body.get("status") != "ready":
        fail(f"/ready unexpected data: {ready_body}")
    ok("/ready")

    # 3. Auth required on enrich
    try:
        unauth = requests.post(
            f"{BASE_URL}/enrich/sync",
            json={"username": "smoke-user", "requested_tiers": ["tier2"]},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        fail(f"unauth /enrich/sync unreachable: {exc}")
    if unauth.status_code != 401:
        fail(f"unauth /enrich/sync expected 401, got {unauth.status_code}")
    ok("unauth /enrich/sync → 401")

    # 4. Sync enrich with Bearer
    try:
        enrich = requests.post(
            f"{BASE_URL}/enrich/sync",
            headers=auth_headers(),
            json={"username": "smoke-user", "requested_tiers": ["tier2"]},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        fail(f"/enrich/sync unreachable: {exc}")
    if enrich.status_code != 200:
        fail(f"/enrich/sync expected 200, got {enrich.status_code}: {enrich.text[:200]}")
    payload = unwrap_success(enrich.json(), "/enrich/sync")
    if "status" not in payload:
        fail(f"/enrich/sync missing status: {payload}")
    dossier = payload.get("dossier")
    if not isinstance(dossier, dict):
        fail(f"/enrich/sync missing dossier object: {payload}")
    for key in ("handles", "confidence", "sources", "metadata"):
        if key not in dossier:
            fail(f"/enrich/sync dossier missing {key!r}")
    ok(f"/enrich/sync → {payload['status']}")

    # 5. Opt-out without Bearer (public compliance route)
    opt_id = f"smoke-optout-{uuid.uuid4().hex}@example.com"
    try:
        opt_out = requests.post(
            f"{BASE_URL}/api/opt-out",
            json={"identifier": opt_id, "reason": "smoke-test"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        fail(f"/api/opt-out unreachable: {exc}")
    if opt_out.status_code != 202:
        fail(f"/api/opt-out expected 202, got {opt_out.status_code}: {opt_out.text[:200]}")
    ok("unauth /api/opt-out → 202")

    # 6. DSAR without Bearer (public compliance route)
    dsar_id = f"smoke-dsar-{uuid.uuid4().hex}@example.com"
    try:
        dsar = requests.post(
            f"{BASE_URL}/api/dsar",
            json={"identifier": dsar_id, "request_type": "access"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        fail(f"/api/dsar unreachable: {exc}")
    if dsar.status_code != 201:
        fail(f"/api/dsar expected 201, got {dsar.status_code}: {dsar.text[:200]}")
    dsar_body = unwrap_success(dsar.json(), "/api/dsar")
    if "id" not in dsar_body:
        fail(f"/api/dsar missing id: {dsar_body}")
    ok("unauth /api/dsar → 201")

    if SKIP_ASYNC:
        print("smoke ok (async skipped)")
        return

    # 7. Async enrich + poll (requires worker + redis)
    try:
        async_resp = requests.post(
            f"{BASE_URL}/enrich",
            headers={**auth_headers(), "Content-Type": "application/json"},
            json={"username": "smoke-async-user", "requested_tiers": ["tier2"]},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        fail(f"/enrich unreachable: {exc}")
    if async_resp.status_code != 202:
        fail(f"/enrich expected 202, got {async_resp.status_code}: {async_resp.text[:200]}")
    async_body = unwrap_success(async_resp.json(), "/enrich")
    if async_body.get("status") != "queued":
        fail(f"/enrich expected status queued, got: {async_body}")
    job_id = async_body.get("id")
    if not job_id:
        fail(f"/enrich missing job id: {async_body}")
    ok(f"/enrich → queued (job_id={job_id})")

    deadline = time.time() + POLL_DEADLINE
    final: dict | None = None
    while time.time() < deadline:
        try:
            poll = requests.get(f"{BASE_URL}/enrich/{job_id}", headers=auth_headers(), timeout=TIMEOUT)
        except requests.RequestException as exc:
            fail(f"/enrich/{job_id} poll unreachable: {exc}")
        if poll.status_code != 200:
            fail(f"/enrich/{job_id} expected 200, got {poll.status_code}: {poll.text[:200]}")
        final = unwrap_success(poll.json(), f"/enrich/{job_id}")
        if final.get("status") not in ("queued", "running"):
            break
        time.sleep(POLL_INTERVAL)

    if final is None:
        fail("async poll returned no response")
    terminal_status = final.get("status")
    if terminal_status != "completed":
        fail(f"async job did not complete: status={terminal_status!r} body={final}")
    async_dossier = final.get("dossier")
    if not isinstance(async_dossier, dict) or not async_dossier.get("handles"):
        fail(f"async job missing dossier handles: {final}")
    ok(f"/enrich/{job_id} → {terminal_status}")

    print("smoke ok")


if __name__ == "__main__":
    main()
