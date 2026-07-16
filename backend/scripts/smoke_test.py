"""Short deterministic smoke checks against a running API.

Env:
  BASE_URL   — API root (default http://localhost:8000)
  API_TOKEN  — Bearer token (default change-me)

Exits non-zero on any failure.
"""

from __future__ import annotations

import os
import sys

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.environ.get("API_TOKEN", "change-me")
TIMEOUT = float(os.environ.get("SMOKE_TIMEOUT", "60"))


def fail(msg: str) -> None:
    print(f"FAIL  {msg}", file=sys.stderr)
    raise SystemExit(1)


def ok(msg: str) -> None:
    print(f"PASS  {msg}")


def main() -> None:
    # 1. Liveness
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.RequestException as exc:
        fail(f"/health unreachable: {exc}")
    if health.status_code != 200:
        fail(f"/health expected 200, got {health.status_code}")
    body = health.json()
    if body.get("status") != "ok":
        fail(f"/health unexpected body: {body}")
    ok("/health")

    # 2. Auth required on enrich
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

    # 3. Sync enrich with Bearer
    try:
        enrich = requests.post(
            f"{BASE_URL}/enrich/sync",
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            json={"username": "smoke-user", "requested_tiers": ["tier2"]},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        fail(f"/enrich/sync unreachable: {exc}")
    if enrich.status_code != 200:
        fail(f"/enrich/sync expected 200, got {enrich.status_code}: {enrich.text[:200]}")
    payload = enrich.json()
    if "status" not in payload:
        fail(f"/enrich/sync missing status: {payload}")
    dossier = payload.get("dossier")
    if not isinstance(dossier, dict):
        fail(f"/enrich/sync missing dossier object: {payload}")
    for key in ("handles", "confidence", "sources", "metadata"):
        if key not in dossier:
            fail(f"/enrich/sync dossier missing {key!r}")
    ok(f"/enrich/sync → {payload['status']}")

    print("smoke ok")


if __name__ == "__main__":
    main()
