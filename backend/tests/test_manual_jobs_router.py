"""HTTP tests for the manual job entries router endpoints (Module 4, Module F §10.5, §10.8).

`manual_jobs.router` is registered directly in `app/main.py` as part of this
chunk (§10.5's "Registered in main.py"), so no test-time mounting workaround
is needed (unlike `test_interview_scheduling_router.py`, which predates its
own router's registration).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.main import app
from app.modules.job_matching.models import JobMatch
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _auth_headers(user_id: str | None = None) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": user_id or str(uuid4()),
    }


@pytest.fixture
async def seeded_user(db: AsyncSession) -> dict[str, Any]:
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"manual-jobs-seeded-{user_id.hex[:8]}@example.com",
        first_name="Seeded",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    return {"user_id": user_id}


# ---------------------------------------------------------------------------
# POST /api/manual-jobs
# ---------------------------------------------------------------------------


def test_create_manual_job_entry_happy_path(
    client: TestClient, seeded_user: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))

    response = client.post(
        "/api/manual-jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "company": "Acme Corp",
            "location": "Remote",
            "source_label": "Referral from a friend",
            "source_url": "https://example.com/careers/123",
            "notes": "Met the hiring manager at a meetup",
        },
    )
    data = assert_success(response)

    assert data["title"] == "Backend Engineer"
    assert data["company"] == "Acme Corp"
    assert data["location"] == "Remote"
    assert data["source_label"] == "Referral from a friend"
    assert data["source_url"] == "https://example.com/careers/123"
    assert data["notes"] == "Met the hiring manager at a meetup"
    assert data["id"]
    assert data["job_match_id"]
    assert data["created_at"]


def test_create_manual_job_entry_minimal_fields(
    client: TestClient, seeded_user: dict[str, Any]
) -> None:
    """Only title + company are required; every optional field can be omitted."""
    headers = _auth_headers(str(seeded_user["user_id"]))

    response = client.post(
        "/api/manual-jobs",
        headers=headers,
        json={"title": "Data Analyst", "company": "Startup Inc"},
    )
    data = assert_success(response)

    assert data["title"] == "Data Analyst"
    assert data["company"] == "Startup Inc"
    assert data["location"] is None
    assert data["source_label"] is None
    assert data["source_url"] is None
    assert data["notes"] is None


def test_create_manual_job_entry_missing_required_field_returns_422(
    client: TestClient, seeded_user: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))

    response = client.post("/api/manual-jobs", headers=headers, json={"title": "No Company"})
    assert_error(response, 422, "VALIDATION_ERROR")


async def test_create_manual_job_entry_creates_companion_job_match(
    client: TestClient, seeded_user: dict[str, Any], db: AsyncSession
) -> None:
    """§10.2/§10.5: the create endpoint must produce a real JobMatch row with
    manual_job_entry_id set and job_posting_id NULL — the whole point of the
    schema change this chunk lands."""
    headers = _auth_headers(str(seeded_user["user_id"]))

    data = assert_success(
        client.post(
            "/api/manual-jobs",
            headers=headers,
            json={"title": "Platform Engineer", "company": "Beta LLC"},
        )
    )

    result = await db.execute(select(JobMatch).where(JobMatch.id == UUID(data["job_match_id"])))
    match = result.scalar_one()
    assert match.job_posting_id is None
    assert str(match.manual_job_entry_id) == data["id"]
    assert match.overall_score == 0.0
    assert match.similarity_score == 0.0
    assert match.rule_score == 0.0
    assert match.score_breakdown == {}
    assert match.application_status == "new"
    assert str(match.user_id) == str(seeded_user["user_id"])


def test_create_manual_job_entry_requires_auth(client: TestClient) -> None:
    response = client.post("/api/manual-jobs", json={"title": "No Auth", "company": "Nope Inc"})
    assert response.status_code in (401, 403)


async def test_create_manual_job_entry_is_scoped_to_the_authenticated_user(
    client: TestClient, seeded_user: dict[str, Any], db: AsyncSession
) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))
    data = assert_success(
        client.post(
            "/api/manual-jobs",
            headers=headers,
            json={"title": "Owned Entry", "company": "Owner Co"},
        )
    )

    result = await db.execute(select(JobMatch).where(JobMatch.id == UUID(data["job_match_id"])))
    match = result.scalar_one()
    assert str(match.user_id) == str(seeded_user["user_id"])


# ---------------------------------------------------------------------------
# §14 non-goal: v1 is create-only — no PATCH/DELETE, no GET beyond what §10.5
# explicitly specifies (which is nothing — the plan's router.py only defines
# the POST route).
# ---------------------------------------------------------------------------


def test_no_get_list_route_exists(client: TestClient, seeded_user: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))
    response = client.get("/api/manual-jobs", headers=headers)
    assert response.status_code in (404, 405)


def test_no_get_by_id_route_exists(client: TestClient, seeded_user: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))
    data = assert_success(
        client.post(
            "/api/manual-jobs",
            headers=headers,
            json={"title": "Immutable Entry", "company": "Locked Co"},
        )
    )
    response = client.get(f"/api/manual-jobs/{data['id']}", headers=headers)
    assert response.status_code in (404, 405)


def test_no_patch_route_exists(client: TestClient, seeded_user: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))
    data = assert_success(
        client.post(
            "/api/manual-jobs",
            headers=headers,
            json={"title": "Immutable Entry", "company": "Locked Co"},
        )
    )
    response = client.patch(
        f"/api/manual-jobs/{data['id']}", headers=headers, json={"title": "Edited"}
    )
    assert response.status_code in (404, 405)


def test_no_delete_route_exists(client: TestClient, seeded_user: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))
    data = assert_success(
        client.post(
            "/api/manual-jobs",
            headers=headers,
            json={"title": "Immutable Entry", "company": "Locked Co"},
        )
    )
    response = client.delete(f"/api/manual-jobs/{data['id']}", headers=headers)
    assert response.status_code in (404, 405)


def test_no_patch_route_on_collection_url(client: TestClient, seeded_user: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))
    response = client.patch("/api/manual-jobs", headers=headers, json={"title": "Edited"})
    assert response.status_code in (404, 405)


def test_no_delete_route_on_collection_url(client: TestClient, seeded_user: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_user["user_id"]))
    response = client.delete("/api/manual-jobs", headers=headers)
    assert response.status_code in (404, 405)
