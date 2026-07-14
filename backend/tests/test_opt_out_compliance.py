"""Opt-out compliance: suppression, audit trail, and data purge."""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import AuditLog, JobRecord
from app.storage.db import SessionLocal, init_db


def test_opt_out_registers_suppression_audit_and_purges_jobs() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer change-me"}
    identifier = f"purge-me-{uuid4().hex}@example.com"

    enrich = client.post(
        "/enrich/sync",
        headers=headers,
        json={"email": identifier, "requested_tiers": ["tier2"]},
    )
    assert enrich.status_code == 200
    assert enrich.json()["status"] == "completed"
    job_id = enrich.json()["id"]

    opt_out = client.post(
        "/api/opt-out",
        headers=headers,
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

    import asyncio

    asyncio.run(_assert_purged())

    blocked = client.post(
        "/enrich/sync",
        headers=headers,
        json={"email": identifier, "requested_tiers": ["tier2"]},
    )
    assert blocked.json()["status"] == "suppressed"
