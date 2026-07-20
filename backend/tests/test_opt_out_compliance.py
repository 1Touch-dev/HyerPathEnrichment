"""Opt-out compliance: suppression, audit trail, and data purge."""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.compliance.models import AuditLog
from app.database.session import SessionLocal, init_db
from app.modules.enrichment.models import JobRecord


def test_opt_out_registers_suppression_audit_and_purges_jobs() -> None:
    client = TestClient(app)
    enrich_headers = {"Authorization": "Bearer change-me"}
    identifier = f"purge-me-{uuid4().hex}@example.com"

    enrich = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "optout-user", "requested_tiers": ["tier2"]},
    )
    assert enrich.status_code == 200
    assert enrich.json()["data"]["status"] == "completed"
    job_id = enrich.json()["data"]["id"]

    # Opt-out is public — no Authorization header.
    opt_out = client.post(
        "/api/opt-out",
        json={"identifier": identifier, "reason": "gdpr"},
    )
    assert opt_out.status_code == 202

    async def _assert_purged() -> None:
        await init_db()
        async with SessionLocal() as session:
            job = await session.get(JobRecord, job_id)
            assert job is not None
            assert job.status == "purged"
            assert job.dossier_payload == {}

            audit = await session.execute(select(AuditLog))
            events = {row.event_type for row in audit.scalars().all()}
            assert "opt_out" in events
            assert "data_purged" in events

    asyncio.run(_assert_purged())

    blocked = client.post(
        "/enrich/sync",
        headers=enrich_headers,
        json={"email": identifier, "username": "optout-user", "requested_tiers": ["tier2"]},
    )
    assert blocked.json()["data"]["status"] == "suppressed"


def test_opt_out_and_check_work_without_bearer() -> None:
    client = TestClient(app)
    identifier = f"public-optout-{uuid4().hex}@example.com"

    opt_out = client.post("/api/opt-out", json={"identifier": identifier, "reason": "gdpr"})
    assert opt_out.status_code == 202

    check = client.get("/api/opt-out/check", params={"identifier": identifier})
    assert check.status_code == 200
    assert check.json()["data"]["suppressed"] is True


def test_enrich_still_requires_bearer() -> None:
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        json={"email": f"needs-auth-{uuid4().hex}@example.com", "username": "needs-auth", "requested_tiers": ["tier2"]},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "unauthorized"
