"""Integration tests for GET /api/demand-intelligence/top-countries
(machine-2-parallel-tracks/02) against a seeded DB, end-to-end through the router.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.modules.demand_intelligence.models import CountryDemandSnapshot
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


async def _seed_snapshot(db: AsyncSession, **overrides: object) -> CountryDemandSnapshot:
    fields: dict[str, object] = {
        "snapshot_date": date(2026, 8, 25),
        "country_iso2": "us",
        "role_bucket": "backend engineer",
        "posting_count": 10,
        "remote_posting_count": 3,
        "avg_salary_min": 100_000,
        "avg_salary_max": 140_000,
    }
    fields.update(overrides)
    snapshot = CountryDemandSnapshot(**fields)
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def test_top_countries_happy_path(
    client: TestClient, db: AsyncSession, superuser, auth_headers
) -> None:
    role = f"integration role {uuid.uuid4().hex[:8]}"
    snap_date = date(2026, 8, 25)
    await _seed_snapshot(
        db, snapshot_date=snap_date, country_iso2="us", role_bucket=role, posting_count=5
    )
    await _seed_snapshot(
        db, snapshot_date=snap_date, country_iso2="in", role_bucket=role, posting_count=50
    )

    response = client.get(
        "/api/demand-intelligence/top-countries",
        params={"role": role},
        headers=auth_headers(superuser.id),
    )
    data = assert_success(response)

    assert data["role"] == role
    assert len(data["results"]) == 2
    # Ordered by posting_count descending.
    assert data["results"][0]["country_iso2"] == "in"
    assert data["results"][0]["posting_count"] == 50
    assert data["results"][0]["tier"] in ("tier_1", "tier_2", "tier_3")
    assert data["results"][1]["country_iso2"] == "us"
    # "us" is a fixed Tier 1 country regardless of its relative posting_count here.
    assert data["results"][1]["tier"] == "tier_1"


async def test_top_countries_no_match_returns_empty_results(
    client: TestClient, superuser, auth_headers
) -> None:
    response = client.get(
        "/api/demand-intelligence/top-countries",
        params={"role": f"no-such-role-{uuid.uuid4().hex}"},
        headers=auth_headers(superuser.id),
    )
    data = assert_success(response)
    assert data["results"] == []


async def test_top_countries_respects_limit_param(
    client: TestClient, db: AsyncSession, superuser, auth_headers
) -> None:
    role = f"limit role {uuid.uuid4().hex[:8]}"
    snap_date = date(2026, 8, 25)
    for i, country in enumerate(["us", "gb", "in", "ae", "sg"]):
        await _seed_snapshot(
            db, snapshot_date=snap_date, country_iso2=country, role_bucket=role, posting_count=i + 1
        )

    response = client.get(
        "/api/demand-intelligence/top-countries",
        params={"role": role, "limit": 2},
        headers=auth_headers(superuser.id),
    )
    data = assert_success(response)
    assert len(data["results"]) == 2


def test_top_countries_requires_auth(client: TestClient) -> None:
    response = client.get("/api/demand-intelligence/top-countries", params={"role": "engineer"})
    assert response.status_code in (401, 403)


def test_top_countries_missing_role_param_returns_422(
    client: TestClient, superuser, auth_headers
) -> None:
    response = client.get(
        "/api/demand-intelligence/top-countries",
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 422, "VALIDATION_ERROR")
