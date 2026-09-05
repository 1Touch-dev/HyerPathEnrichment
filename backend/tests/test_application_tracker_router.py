"""HTTP tests for the application tracker router endpoints (via TestClient)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.main import app
from app.modules.job_matching.models import JobMatch, JobPosting
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
async def seeded_match(db: AsyncSession) -> dict[str, Any]:
    """Insert a User + JobPosting + JobMatch directly, bypassing service/repository layers."""
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"tracker-seeded-{user_id.hex[:8]}@example.com",
        first_name="Seeded",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)

    posting = JobPosting(
        dedup_key=f"dedup-{uuid4().hex}",
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="Remote",
        remote=True,
        source="linkedin",
        source_url="https://linkedin.com/jobs/123",
    )
    db.add(posting)
    await db.commit()
    await db.refresh(posting)

    match = JobMatch(
        user_id=user_id,
        job_posting_id=posting.id,
        similarity_score=0.9,
        rule_score=0.8,
        overall_score=86.0,
        score_breakdown={"salary_fit": 1.0, "location_fit": 1.0},
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)

    return {"user_id": user_id, "posting": posting, "match": match}


# ---------------------------------------------------------------------------
# GET /api/application-tracker/matches
# ---------------------------------------------------------------------------


def test_list_tracked_matches_empty_for_new_user(client: TestClient) -> None:
    response = client.get("/api/application-tracker/matches", headers=_auth_headers())
    data = assert_success(response)

    assert data["matches"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert data["counts_by_status"] == {
        "new": 0,
        "applied": 0,
        "replied": 0,
        "interview": 0,
        "offer": 0,
        "rejected": 0,
    }


def test_list_tracked_matches_returns_seeded_match(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))

    response = client.get("/api/application-tracker/matches", headers=headers)
    data = assert_success(response)

    assert data["total"] == 1
    assert len(data["matches"]) == 1

    match_payload = data["matches"][0]
    posting = seeded_match["posting"]
    match = seeded_match["match"]

    assert match_payload["match_id"] == str(match.id)
    assert match_payload["job_posting_id"] == str(posting.id)
    assert match_payload["title"] == "Senior Backend Engineer"
    assert match_payload["company"] == "Acme Corp"
    assert match_payload["overall_score"] == 86.0
    assert match_payload["application_status"] == "new"
    assert match_payload["status_updated_at"] is None
    assert match_payload["next_interview_at"] is None
    assert data["counts_by_status"]["new"] == 1


def test_list_tracked_matches_status_filter(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    client.patch(
        f"/api/application-tracker/matches/{match_id}/status",
        headers=headers,
        json={"application_status": "applied"},
    )

    matching = client.get(
        "/api/application-tracker/matches", headers=headers, params={"status": "applied"}
    )
    matching_data = assert_success(matching)
    assert matching_data["total"] == 1

    non_matching = client.get(
        "/api/application-tracker/matches", headers=headers, params={"status": "rejected"}
    )
    non_matching_data = assert_success(non_matching)
    assert non_matching_data["total"] == 0


def test_list_tracked_matches_other_users_match_not_returned(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    other_user_headers = _auth_headers()  # different (fresh) user id

    response = client.get("/api/application-tracker/matches", headers=other_user_headers)
    data = assert_success(response)

    assert data["total"] == 0
    assert data["matches"] == []


# ---------------------------------------------------------------------------
# PATCH /api/application-tracker/matches/{match_id}/status
# ---------------------------------------------------------------------------


def test_update_application_status_full_round_trip(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.patch(
        f"/api/application-tracker/matches/{match_id}/status",
        headers=headers,
        json={"application_status": "interview"},
    )
    data = assert_success(response)

    assert data["match_id"] == match_id
    assert data["application_status"] == "interview"
    assert data["status_updated_at"] is not None

    fetched = client.get("/api/application-tracker/matches", headers=headers)
    fetched_data = assert_success(fetched)
    assert fetched_data["matches"][0]["application_status"] == "interview"
    assert fetched_data["counts_by_status"]["interview"] == 1
    assert fetched_data["counts_by_status"]["new"] == 0


def test_update_application_status_invalid_value_returns_422(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.patch(
        f"/api/application-tracker/matches/{match_id}/status",
        headers=headers,
        json={"application_status": "ghosted"},
    )
    assert response.status_code == 422


def test_update_application_status_foreign_match_id_returns_404(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    """A match_id belonging to a different user 404s rather than leaking or mutating it."""
    other_user_headers = _auth_headers()  # different (fresh) user id
    match_id = str(seeded_match["match"].id)

    response = client.patch(
        f"/api/application-tracker/matches/{match_id}/status",
        headers=other_user_headers,
        json={"application_status": "applied"},
    )
    assert_error(response, 404, "NOT_FOUND")


def test_update_application_status_bogus_match_id_returns_404(client: TestClient) -> None:
    headers = _auth_headers()
    bogus_id = str(uuid4())

    response = client.patch(
        f"/api/application-tracker/matches/{bogus_id}/status",
        headers=headers,
        json={"application_status": "applied"},
    )
    assert_error(response, 404, "NOT_FOUND")


# ---------------------------------------------------------------------------
# Module B integration (§7.5): mark-applied auto-advance / non-downgrade
# ---------------------------------------------------------------------------


def test_mark_applied_auto_advances_new_to_applied(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    """Module B's `mark-applied` endpoint auto-advances a still-`new` match's
    application_status to `applied` (§7.5)."""
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    tracked_before = assert_success(client.get("/api/application-tracker/matches", headers=headers))
    assert tracked_before["matches"][0]["application_status"] == "new"

    response = client.post(
        f"/api/job-matching/matches/{match_id}/mark-applied",
        headers=headers,
        json={"applied": True},
    )
    assert response.status_code == 204

    tracked_after = assert_success(client.get("/api/application-tracker/matches", headers=headers))
    assert tracked_after["matches"][0]["application_status"] == "applied"
    assert tracked_after["matches"][0]["status_updated_at"] is not None


def test_mark_applied_does_not_downgrade_interview_status(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    """A candidate who already manually advanced to `interview` and then (re-)marks
    the match as applied (e.g. toggling the mark-as-applied checkbox again) must NOT
    have their status silently reset back to `applied` (§7.5's "never downgrade" rule).
    """
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    # Manually advance past "applied" first.
    client.patch(
        f"/api/application-tracker/matches/{match_id}/status",
        headers=headers,
        json={"application_status": "interview"},
    )

    response = client.post(
        f"/api/job-matching/matches/{match_id}/mark-applied",
        headers=headers,
        json={"applied": True},
    )
    assert response.status_code == 204

    tracked_after = assert_success(client.get("/api/application-tracker/matches", headers=headers))
    assert tracked_after["matches"][0]["application_status"] == "interview"


def test_mark_applied_unmark_does_not_change_status(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    """Unmarking applied (applied=False) never touches application_status — the
    auto-advance hook only fires on the applied=True path (§7.5)."""
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    client.post(
        f"/api/job-matching/matches/{match_id}/mark-applied",
        headers=headers,
        json={"applied": True},
    )
    client.post(
        f"/api/job-matching/matches/{match_id}/mark-applied",
        headers=headers,
        json={"applied": False},
    )

    tracked_after = assert_success(client.get("/api/application-tracker/matches", headers=headers))
    # Auto-advanced to "applied" on the first call; unmarking doesn't revert it.
    assert tracked_after["matches"][0]["application_status"] == "applied"


# ---------------------------------------------------------------------------
# Auth requirements
# ---------------------------------------------------------------------------

_UNAUTHENTICATED_REQUESTS = [
    ("GET", "/api/application-tracker/matches", None),
    (
        "PATCH",
        f"/api/application-tracker/matches/{uuid4()}/status",
        {"application_status": "applied"},
    ),
]


@pytest.mark.parametrize("method,path,body", _UNAUTHENTICATED_REQUESTS)
def test_endpoints_require_auth(
    client: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = client.request(method, path, json=body)
    body_json = assert_error(response, 401, "UNAUTHORIZED")
    assert body_json["error"]["message"] == "Invalid or missing authorization"
