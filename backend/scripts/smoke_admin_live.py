#!/usr/bin/env python3
"""End-to-end HTTP smoke test for the Admin Module against a real, running
backend (Postgres + Redis + API container) — no mocks, no test client.

Seeds a superuser and a second regular user directly in the DB (same
direct-row-write pattern as `create_test_user.py`), then drives the full
Admin Module surface purely over HTTP: login, user list/suspend, feature
flags, MFA enrollment, impersonation start/end, queues overview, system
health, and a review-queue flag -> decide -> domain-flip -> audit pass —
printing a PASS/FAIL line per step and exiting non-zero on any failure.

Usage:
    python scripts/smoke_admin_live.py [--base-url http://127.0.0.1:8010]

The base URL can also be set via the ADMIN_SMOKE_BASE_URL env var.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
import pyotp

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_DEFAULT_BASE_URL = "http://127.0.0.1:8010"

_SUPERUSER_EMAIL = "admin-smoke-superuser@example.com"
_SUPERUSER_PASSWORD = "AdminSmokeSuperuser123"
_TARGET_EMAIL = "admin-smoke-target@example.com"
_TARGET_PASSWORD = "AdminSmokeTarget123"


class StepResult:
    def __init__(self, name: str) -> None:
        self.name = name
        self.passed = False
        self.detail = ""


_results: list[StepResult] = []


def _record(name: str, passed: bool, detail: str = "") -> None:
    result = StepResult(name)
    result.passed = passed
    result.detail = detail
    _results.append(result)
    status = "PASS" if passed else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)


async def _seed_users() -> tuple[uuid.UUID, uuid.UUID]:
    """Create (or reuse) a superuser and a regular target user directly in the DB,
    mirroring create_test_user.py's direct-row-write pattern."""
    from sqlalchemy import select

    import app.database.orm_registry  # noqa: F401  (registers all ORM models/relationships)
    from app.auth.models import User
    from app.auth.password import hash_password
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        superuser_result = await session.execute(select(User).where(User.email == _SUPERUSER_EMAIL))
        superuser = superuser_result.scalar_one_or_none()
        if superuser is None:
            superuser = User(
                email=_SUPERUSER_EMAIL,
                hashed_password=hash_password(_SUPERUSER_PASSWORD),
                first_name="Admin",
                last_name="Smoke",
                is_verified=True,
                is_active=True,
                is_superuser=True,
            )
            session.add(superuser)
        else:
            superuser.hashed_password = hash_password(_SUPERUSER_PASSWORD)
            superuser.is_verified = True
            superuser.is_active = True
            superuser.deleted_at = None
            superuser.is_superuser = True
            # Reset MFA state so re-runs against a persistent DB behave like a fresh enroll.
            superuser.mfa_enabled = False
            superuser.mfa_secret = None
            superuser.mfa_enrolled_at = None

        target_result = await session.execute(select(User).where(User.email == _TARGET_EMAIL))
        target = target_result.scalar_one_or_none()
        if target is None:
            target = User(
                email=_TARGET_EMAIL,
                hashed_password=hash_password(_TARGET_PASSWORD),
                first_name="Target",
                last_name="Smoke",
                is_verified=True,
                is_active=True,
                is_superuser=False,
            )
            session.add(target)
        else:
            target.hashed_password = hash_password(_TARGET_PASSWORD)
            target.is_verified = True
            target.is_active = True
            target.deleted_at = None
            target.is_superuser = False

        await session.commit()
        superuser_id, target_id = superuser.id, target.id

    # Dispose the module-level async engine's connection pool before this
    # asyncio.run() call's event loop closes — otherwise a later asyncio.run()
    # call (e.g. _seed_flagged_job_posting()) reusing the same global `engine`
    # trips "attached to a different loop" when the pool tries to reuse an
    # asyncpg connection bound to this (now-closed) loop.
    from app.database.session import engine

    await engine.dispose()
    return superuser_id, target_id


_FLAGGED_JOB_TITLE = "Remote Data Entry Clerk"
_FLAGGED_JOB_COMPANY = "Admin Smoke Test Co"
# Real deny-listed term from moderation_flagging._DENY_LIST — see that module
# for the full list. Using a real entry (rather than inventing one) ensures
# this exercises the actual heuristic match, not a hand-crafted assumption.
_FLAGGED_JOB_DESCRIPTION = "This role offers guaranteed income with flexible hours."


async def _seed_flagged_job_posting() -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a `job_posting` row directly in the DB (mirroring `_seed_users()`'s
    direct-row-write pattern), containing a deny-listed heuristic term in its
    description, then call the real `flag_if_needed()` cascade against it —
    the same function the scan pipeline calls — so the resulting
    `admin_review_queue` row is produced by real code, not a hand-crafted
    insert. Returns (job_posting_id, review_queue_item_id)."""
    import app.database.orm_registry  # noqa: F401  (registers all ORM models/relationships)
    from app.database.session import SessionLocal
    from app.modules.admin.moderation_flagging import flag_if_needed
    from app.modules.job_matching.models import JobPosting

    posting_id = uuid.uuid4()

    async with SessionLocal() as session:
        posting = JobPosting(
            id=posting_id,
            dedup_key=f"admin-smoke-flagged-{posting_id}",
            title=_FLAGGED_JOB_TITLE,
            company=_FLAGGED_JOB_COMPANY,
            source="admin_smoke_test",
            description_raw=_FLAGGED_JOB_DESCRIPTION,
        )
        session.add(posting)
        await session.flush()

        item = await flag_if_needed(
            session,
            resource_type="job_posting",
            resource_id=posting_id,
            text_fields=[_FLAGGED_JOB_TITLE, _FLAGGED_JOB_DESCRIPTION],
        )
        await session.commit()

    # See _seed_users()'s comment: dispose the shared engine's pool before
    # this event loop closes, since this is the last asyncio.run() call in
    # the script but leaves pooled connections tied to a soon-dead loop
    # otherwise.
    from app.database.session import engine

    await engine.dispose()

    if item is None:
        raise RuntimeError(
            "flag_if_needed() did not flag the seeded job posting — deny-list term "
            "may have changed; check moderation_flagging._DENY_LIST"
        )
    return posting_id, item.id


def _login(client: httpx.Client, email: str, password: str) -> httpx.Response:
    return client.post("/auth/login", json={"email": email, "password": password})


def run_smoke(base_url: str) -> bool:
    superuser_id, target_id = asyncio.run(_seed_users())
    _record(
        "seed superuser + target user in DB", True, f"superuser={superuser_id} target={target_id}"
    )

    client = httpx.Client(base_url=base_url, timeout=15.0)
    try:
        # --- Login as superuser ---
        resp = _login(client, _SUPERUSER_EMAIL, _SUPERUSER_PASSWORD)
        _record(
            "POST /auth/login (superuser)", resp.status_code == 200, f"status={resp.status_code}"
        )
        if resp.status_code != 200:
            return False

        # --- List users, assert cursor shape ---
        resp = client.get("/api/admin/users")
        ok = resp.status_code == 200
        if ok:
            data = resp.json().get("data", {})
            ok = "items" in data and "next_cursor" in data and "has_more" in data
        _record("GET /api/admin/users (cursor shape)", ok, f"status={resp.status_code}")

        # --- Suspend the target user (exercises Part A's audit fallback fix on a UUID PATCH path) ---
        resp = client.patch(
            f"/api/admin/users/{target_id}/status",
            json={"is_active": False, "reason": "smoke test"},
        )
        _record(
            "PATCH /api/admin/users/{id}/status (suspend, UUID-path audit fallback)",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )

        # Re-activate so later checks (impersonation target) aren't blocked by is_active=False.
        resp = client.patch(
            f"/api/admin/users/{target_id}/status",
            json={"is_active": True, "reason": "smoke test reactivate"},
        )
        _record(
            "PATCH /api/admin/users/{id}/status (reactivate)",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )

        # --- Feature flag create/flip/read-back (cache invalidation) ---
        flag_key = "admin-smoke-flag"
        resp = client.put(
            f"/api/admin/feature-flags/{flag_key}", json={"enabled": True, "description": "smoke"}
        )
        _record(
            "PUT /api/admin/feature-flags/{key} (enable)",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )

        resp = client.get("/api/admin/feature-flags")
        flags = resp.json().get("data", []) if resp.status_code == 200 else []
        enabled_now = next((f["enabled"] for f in flags if f["key"] == flag_key), None)
        _record(
            "GET /api/admin/feature-flags (reflects enabled=True)",
            enabled_now is True,
            f"enabled_now={enabled_now}",
        )

        resp = client.put(
            f"/api/admin/feature-flags/{flag_key}", json={"enabled": False, "description": "smoke"}
        )
        _record(
            "PUT /api/admin/feature-flags/{key} (disable)",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )

        resp = client.get("/api/admin/feature-flags")
        flags = resp.json().get("data", []) if resp.status_code == 200 else []
        disabled_now = next((f["enabled"] for f in flags if f["key"] == flag_key), None)
        _record(
            "GET /api/admin/feature-flags (reflects enabled=False, no stale cache)",
            disabled_now is False,
            f"enabled_now={disabled_now}",
        )

        # --- MFA enroll + confirm ---
        resp = client.post("/api/admin/mfa/enroll")
        secret = None
        if resp.status_code == 200:
            secret = resp.json().get("data", {}).get("secret")
        _record(
            "POST /api/admin/mfa/enroll",
            resp.status_code == 200 and bool(secret),
            f"status={resp.status_code}",
        )

        mfa_code = pyotp.TOTP(secret).now() if secret else None
        resp2: httpx.Response | None = (
            client.post("/api/admin/mfa/confirm", json={"code": mfa_code}) if mfa_code else None
        )
        _record(
            "POST /api/admin/mfa/confirm",
            resp2 is not None and resp2.status_code == 204,
            f"status={resp2.status_code if resp2 else 'skipped'}",
        )

        resp = client.get("/api/admin/mfa/status")
        mfa_enabled_now = (
            resp.json().get("data", {}).get("mfa_enabled") if resp.status_code == 200 else None
        )
        _record(
            "GET /api/admin/mfa/status (mfa_enabled=True)",
            mfa_enabled_now is True,
            f"mfa_enabled={mfa_enabled_now}",
        )

        # --- Impersonation start (MFA now required) -> audit trail -> end ---
        mfa_code_for_impersonation = pyotp.TOTP(secret).now() if secret else None
        resp = client.post(
            f"/api/admin/impersonation/start/{target_id}",
            json={"reason": "smoke test impersonation", "mfa_code": mfa_code_for_impersonation},
        )
        _record(
            "POST /api/admin/impersonation/start/{id}",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )
        impersonation_started_ok = resp.status_code == 200

        # KNOWN BUG (found live, out of this script's scope to fix): impersonation.py
        # hardcodes `secure=True` on the replacement access_token cookie, unlike every
        # other set_cookie() call in this codebase which uses `settings.COOKIE_SECURE`
        # (default False for local/dev per .env.example). Any RFC-6265-compliant HTTP
        # client — httpx included — silently drops a Secure cookie on a plain-HTTP
        # connection, so impersonation appears to succeed (200) but the swapped
        # identity never actually takes effect for the rest of the session over HTTP.
        # Grab the raw cookie value from the response itself (not the client jar,
        # which correctly refuses to re-send it) so the remaining steps can still
        # exercise the server-side impersonation logic end-to-end.
        impersonation_cookie = (
            resp.cookies.get("access_token") if impersonation_started_ok else None
        )

        if impersonation_started_ok and impersonation_cookie:
            resp = client.get(
                "/api/admin/impersonation/status", cookies={"access_token": impersonation_cookie}
            )
            status_data = resp.json().get("data", {}) if resp.status_code == 200 else {}
            _record(
                "GET /api/admin/impersonation/status (is_impersonating=True as target)",
                status_data.get("is_impersonating") is True,
                f"data={status_data}",
            )

            resp = client.post(
                "/api/admin/impersonation/end", cookies={"access_token": impersonation_cookie}
            )
            _record(
                "POST /api/admin/impersonation/end",
                resp.status_code == 204,
                f"status={resp.status_code}",
            )
        elif impersonation_started_ok:
            _record(
                "GET /api/admin/impersonation/status (is_impersonating=True as target)",
                False,
                "impersonation cookie missing from start response",
            )
            _record("POST /api/admin/impersonation/end", False, "no impersonation cookie captured")

        # Impersonation end clears the access_token cookie entirely — re-login as
        # superuser to restore an authenticated session for the remaining checks.
        client.cookies.clear()
        resp = _login(client, _SUPERUSER_EMAIL, _SUPERUSER_PASSWORD)
        _record(
            "POST /auth/login (re-auth as superuser post-impersonation)",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )

        # Confirm impersonation start/end were recorded in the audit trail.
        resp = client.get(
            "/api/admin/audit-logs", params={"action": "impersonation.started", "limit": 5}
        )
        started_logged = False
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            started_logged = any(str(item.get("target_id")) == str(target_id) for item in items)
        _record(
            "GET /api/admin/audit-logs (impersonation.started recorded)",
            started_logged,
            f"status={resp.status_code}",
        )

        resp = client.get(
            "/api/admin/audit-logs", params={"action": "impersonation.ended", "limit": 5}
        )
        ended_logged = False
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            ended_logged = any(str(item.get("target_id")) == str(target_id) for item in items)
        _record(
            "GET /api/admin/audit-logs (impersonation.ended recorded)",
            ended_logged,
            f"status={resp.status_code}",
        )

        # --- Queues overview + system health (zero live workers is a valid state) ---
        resp = client.get("/api/admin/queues")
        queues_ok = resp.status_code == 200 and "queues" in resp.json().get("data", {})
        _record(
            "GET /api/admin/queues (200 + expected shape)", queues_ok, f"status={resp.status_code}"
        )

        resp = client.get("/api/admin/system-health")
        health_data = resp.json().get("data", {}) if resp.status_code == 200 else {}
        health_ok = (
            resp.status_code == 200 and "database_ok" in health_data and "redis_ok" in health_data
        )
        _record(
            "GET /api/admin/system-health (200 + expected shape)",
            health_ok,
            f"status={resp.status_code} database_ok={health_data.get('database_ok')} redis_ok={health_data.get('redis_ok')}",
        )

        # --- Review queue: flag a job posting, list/detail it, decide (reject),
        # confirm the domain-side moderation column flips and the audit log
        # records the decision. ---
        posting_id, review_item_id = asyncio.run(_seed_flagged_job_posting())
        _record(
            "seed job_posting + flag_if_needed() (real heuristic cascade)",
            True,
            f"posting_id={posting_id} review_item_id={review_item_id}",
        )

        resp = client.get(
            "/api/admin/review-queue", params={"resource_type": "job_posting", "status": "pending"}
        )
        review_list_ok = resp.status_code == 200
        if review_list_ok:
            data = resp.json().get("data", {})
            review_list_ok = "items" in data and "next_cursor" in data and "has_more" in data
            review_list_ok = review_list_ok and any(
                item.get("id") == str(review_item_id) for item in data.get("items", [])
            )
        _record(
            "GET /api/admin/review-queue?resource_type=job_posting&status=pending (cursor shape + seeded item present)",
            review_list_ok,
            f"status={resp.status_code}",
        )

        resp = client.get(f"/api/admin/review-queue/{review_item_id}")
        detail_ok = resp.status_code == 200
        resolved_resource: dict[str, Any] | None = None
        if detail_ok:
            detail_data = resp.json().get("data", {})
            resolved_resource = detail_data.get("resolved_resource")
            detail_ok = (
                resolved_resource is not None
                and resolved_resource.get("id") == str(posting_id)
                and resolved_resource.get("title") == _FLAGGED_JOB_TITLE
            )
        _record(
            "GET /api/admin/review-queue/{id} (resolved_resource reflects seeded job posting)",
            detail_ok,
            f"status={resp.status_code} resolved_resource={resolved_resource}",
        )

        resp = client.post(
            f"/api/admin/review-queue/{review_item_id}/decide",
            json={"status": "rejected", "review_notes": "smoke test rejection"},
        )
        _record(
            "POST /api/admin/review-queue/{id}/decide (reject)",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )

        resp = client.get(f"/api/admin/job-postings/{posting_id}")
        moderation_status_now = (
            resp.json().get("data", {}).get("moderation_status") if resp.status_code == 200 else None
        )
        _record(
            "GET /api/admin/job-postings/{id} (moderation_status flipped to 'removed')",
            moderation_status_now == "removed",
            f"status={resp.status_code} moderation_status={moderation_status_now}",
        )

        resp = client.get(
            "/api/admin/audit-logs", params={"action": "review_queue.decide", "limit": 5}
        )
        decide_logged = False
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            decide_logged = any(
                str(item.get("target_id")) == str(review_item_id) for item in items
            )
        _record(
            "GET /api/admin/audit-logs (review_queue.decide recorded with correct target_id)",
            decide_logged,
            f"status={resp.status_code}",
        )
    finally:
        client.close()

    return all(r.passed for r in _results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live HTTP smoke test for the Admin Module")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ADMIN_SMOKE_BASE_URL", _DEFAULT_BASE_URL),
        help="Base URL of the running backend API (default: %(default)s)",
    )
    args = parser.parse_args()

    print(f"=== Admin Module live smoke test against {args.base_url} ===\n")
    all_passed = run_smoke(args.base_url)

    total = len(_results)
    passed = sum(1 for r in _results if r.passed)
    print(f"\n=== Summary: {passed}/{total} steps passed ===")
    if not all_passed:
        print("FAILED steps:")
        for r in _results:
            if not r.passed:
                print(f"  - {r.name}: {r.detail}")
        return 1

    print("All steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
