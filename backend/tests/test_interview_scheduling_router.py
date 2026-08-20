"""HTTP tests for the interview scheduling router endpoints (Module 4, Module D §8.9).

`interview_scheduling.router` is not registered in `app/main.py` yet — a later
reconciliation step registers it alongside Track E's router (per the Phase 3
orchestration plan). To exercise the real HTTP surface without touching
`app/main.py`, this test module mounts the router onto the already-built
`app` instance at import time, the same way `app/main.py` eventually will
(`app.include_router(router, dependencies=[Depends(current_verified_user)])`).
This only mutates the running `FastAPI` app object for the test process; it
does not edit `app/main.py`'s source.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.main import app, current_verified_user
from app.modules.interview_scheduling.router import router as interview_scheduling_router
from app.modules.job_matching.models import JobMatch, JobPosting
from tests.envelope_helpers import assert_error, assert_success

if not any(getattr(route, "path", "").startswith("/api/interviews") for route in app.routes):
    app.include_router(interview_scheduling_router, dependencies=[Depends(current_verified_user)])


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _mock_interview_reminder_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Interview-reminder enqueue/cancel go through real RQ/rq-scheduler calls
    against Redis — mocked at the call site, same convention
    `test_job_matching_api.py` uses for `Queue` (patched directly rather than
    routed through `FakeRedis`, which doesn't implement the full RQ protocol).
    """
    monkeypatch.setattr("app.workers.queue.enqueue_interview_reminder", MagicMock())
    monkeypatch.setattr("app.workers.queue.cancel_interview_reminder", MagicMock())


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
        email=f"interview-seeded-{user_id.hex[:8]}@example.com",
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


def _future_iso(hours: int = 72) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------------------
# POST /api/interviews/matches/{match_id}/schedule
# GET /api/interviews/matches/{match_id}/schedule
# DELETE /api/interviews/matches/{match_id}/schedule
# ---------------------------------------------------------------------------


def test_schedule_get_cancel_round_trip(client: TestClient, seeded_match: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)
    scheduled_at = _future_iso()

    schedule_response = client.post(
        f"/api/interviews/matches/{match_id}/schedule",
        headers=headers,
        json={"scheduled_at": scheduled_at, "duration_minutes": 45, "notes": "Bring laptop"},
    )
    data = assert_success(schedule_response)

    assert data["job_match_id"] == match_id
    assert data["duration_minutes"] == 45
    assert data["notes"] == "Bring laptop"
    assert data["ics_download_url"] == f"/api/interviews/matches/{match_id}/schedule.ics"
    assert data["google_calendar_link"].startswith("https://calendar.google.com/calendar/render?")
    schedule_id = data["id"]

    get_response = client.get(f"/api/interviews/matches/{match_id}/schedule", headers=headers)
    get_data = assert_success(get_response)
    assert get_data["id"] == schedule_id
    assert get_data["duration_minutes"] == 45

    cancel_response = client.delete(f"/api/interviews/matches/{match_id}/schedule", headers=headers)
    assert cancel_response.status_code == 204

    after_cancel = client.get(f"/api/interviews/matches/{match_id}/schedule", headers=headers)
    assert assert_success(after_cancel) is None


def test_reschedule_upserts_same_row(client: TestClient, seeded_match: dict[str, Any]) -> None:
    """Re-posting to /schedule for the same match updates the existing row rather
    than erroring on the job_match_id UNIQUE constraint (§8.3's upsert_schedule)."""
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    first = assert_success(
        client.post(
            f"/api/interviews/matches/{match_id}/schedule",
            headers=headers,
            json={"scheduled_at": _future_iso(72)},
        )
    )
    second = assert_success(
        client.post(
            f"/api/interviews/matches/{match_id}/schedule",
            headers=headers,
            json={"scheduled_at": _future_iso(96), "notes": "Rescheduled"},
        )
    )

    assert first["id"] == second["id"]
    assert second["notes"] == "Rescheduled"


def test_schedule_in_the_past_returns_422(client: TestClient, seeded_match: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    response = client.post(
        f"/api/interviews/matches/{match_id}/schedule",
        headers=headers,
        json={"scheduled_at": past},
    )
    assert_error(response, 422, "VALIDATION_ERROR")


def test_schedule_foreign_match_id_returns_404(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    other_user_headers = _auth_headers()
    match_id = str(seeded_match["match"].id)

    response = client.post(
        f"/api/interviews/matches/{match_id}/schedule",
        headers=other_user_headers,
        json={"scheduled_at": _future_iso()},
    )
    assert_error(response, 404, "NOT_FOUND")


def test_get_schedule_scoped_to_owner_returns_none_for_other_user(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    """A schedule belonging to one candidate is never visible to a different
    candidate — the lookup is scoped by (job_match_id, user_id), so a different
    user simply sees no schedule rather than leaking someone else's."""
    owner_headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)
    client.post(
        f"/api/interviews/matches/{match_id}/schedule",
        headers=owner_headers,
        json={"scheduled_at": _future_iso()},
    )

    other_user_headers = _auth_headers()
    response = client.get(
        f"/api/interviews/matches/{match_id}/schedule", headers=other_user_headers
    )
    assert assert_success(response) is None


def test_cancel_missing_schedule_is_a_no_op(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.delete(f"/api/interviews/matches/{match_id}/schedule", headers=headers)
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Module C integration (§8.3): auto-advance-to-"interview" / non-downgrade
# ---------------------------------------------------------------------------


def test_schedule_auto_advances_new_to_interview(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    client.post(
        f"/api/interviews/matches/{match_id}/schedule",
        headers=headers,
        json={"scheduled_at": _future_iso()},
    )

    tracked = assert_success(client.get("/api/application-tracker/matches", headers=headers))
    assert tracked["matches"][0]["application_status"] == "interview"
    assert tracked["matches"][0]["status_updated_at"] is not None


def test_schedule_does_not_downgrade_offer_status(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    """A candidate already at "offer" who (re)schedules an interview must NOT
    have their status silently reset back to "interview" (forward-fill-only rule,
    shared via job_matching.service.advance_application_status_if_earlier)."""
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    client.patch(
        f"/api/application-tracker/matches/{match_id}/status",
        headers=headers,
        json={"application_status": "offer"},
    )

    client.post(
        f"/api/interviews/matches/{match_id}/schedule",
        headers=headers,
        json={"scheduled_at": _future_iso()},
    )

    tracked = assert_success(client.get("/api/application-tracker/matches", headers=headers))
    assert tracked["matches"][0]["application_status"] == "offer"


# ---------------------------------------------------------------------------
# GET /api/interviews/matches/{match_id}/schedule.ics
# ---------------------------------------------------------------------------


def test_ics_download_headers_and_vevent_markers(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)
    client.post(
        f"/api/interviews/matches/{match_id}/schedule",
        headers=headers,
        json={"scheduled_at": _future_iso(), "duration_minutes": 30},
    )

    response = client.get(f"/api/interviews/matches/{match_id}/schedule.ics", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "charset=utf-8" in response.headers["content-type"]
    assert response.headers["content-disposition"].startswith("attachment;")
    assert ".ics" in response.headers["content-disposition"]

    body = response.text
    assert "BEGIN:VEVENT" in body
    assert "DTSTART:" in body
    assert "DTEND:" in body
    assert "END:VEVENT" in body
    assert "\r\n" in body  # RFC 5545 §3.1: CRLF line endings


def test_ics_escapes_special_characters_in_notes(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)
    client.post(
        f"/api/interviews/matches/{match_id}/schedule",
        headers=headers,
        json={
            "scheduled_at": _future_iso(),
            "notes": "Round 2; bring resume, cover letter\nAsk about PTO",
        },
    )

    response = client.get(f"/api/interviews/matches/{match_id}/schedule.ics", headers=headers)
    body = response.text

    assert "DESCRIPTION:Round 2\\; bring resume\\, cover letter\\nAsk about PTO" in body


def test_ics_404_when_no_schedule_exists(client: TestClient, seeded_match: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.get(f"/api/interviews/matches/{match_id}/schedule.ics", headers=headers)
    assert_error(response, 404, "NOT_FOUND")


def test_ics_404_for_other_users_match(client: TestClient, seeded_match: dict[str, Any]) -> None:
    other_user_headers = _auth_headers()
    match_id = str(seeded_match["match"].id)

    response = client.get(
        f"/api/interviews/matches/{match_id}/schedule.ics", headers=other_user_headers
    )
    assert_error(response, 404, "NOT_FOUND")
