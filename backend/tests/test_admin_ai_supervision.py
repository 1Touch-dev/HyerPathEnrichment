"""AI-agent supervision (audit/oversight) view tests.

See task-orchestration/machine-2-parallel-tracks/04-rbac-admin-platform.md's
"AI-agent supervision (audit/oversight view)" section: `GET /api/admin/ai-actions`
(filterable list) and `GET /api/admin/ai-actions/{id}` (drill-down), both gated by
`require_permission("ai_supervision", "read")`, plus the shared `record_ai_action()`
write helper.

`ai_action_audit_log` is a shared, session-scoped table across the whole test
run (see test_admin_pagination.py's identical note re: `users`) -- every test
below scopes its assertions to rows it itself created (via a fresh, unique
`candidate_user_id`/`triggered_by_user_id` per test) rather than asserting on
the full unfiltered list.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.admin import ai_supervision_service
from app.modules.admin.ai_supervision_models import AiActionAuditLog
from tests.envelope_helpers import assert_error, assert_success

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------


async def test_list_ai_actions_403_without_permission(client, regular_user, auth_headers):
    response = client.get("/api/admin/ai-actions", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_get_ai_action_403_without_permission(client, regular_user, auth_headers):
    response = client.get(f"/api/admin/ai-actions/{uuid4()}", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


# ---------------------------------------------------------------------------
# record_ai_action() unit test
# ---------------------------------------------------------------------------


async def test_record_ai_action_persists_row_with_given_fields(db_session):
    candidate_id = uuid4()
    recruiter_id = uuid4()
    related_id = uuid4()

    row = await ai_supervision_service.record_ai_action(
        db_session,
        action_type="autonomous_apply",
        candidate_user_id=candidate_id,
        triggered_by_user_id=recruiter_id,
        related_id=related_id,
        summary="applied to Acme Corp",
    )

    assert row.id is not None
    assert row.action_type == "autonomous_apply"
    assert row.candidate_user_id == candidate_id
    assert row.triggered_by_user_id == recruiter_id
    assert row.related_id == related_id
    assert row.summary == "applied to Acme Corp"
    assert row.created_at is not None

    fetched = await ai_supervision_service.get_ai_action(db_session, row.id)
    assert fetched is not None
    assert fetched.id == row.id


async def test_record_ai_action_defaults_triggered_by_and_related_to_none(db_session):
    """resume_tailoring rows have no recruiter in the loop and nothing persisted
    to point at (per the doc's named tension) -- both must be optional."""
    candidate_id = uuid4()

    row = await ai_supervision_service.record_ai_action(
        db_session,
        action_type="resume_tailoring",
        candidate_user_id=candidate_id,
        summary="target_company=Acme, target_role=Engineer",
    )

    assert row.triggered_by_user_id is None
    assert row.related_id is None


# ---------------------------------------------------------------------------
# List endpoint: seed one row per action_type, assert all three returned
# ---------------------------------------------------------------------------


async def test_list_returns_all_three_seeded_action_types(
    client, superuser, auth_headers, db_session
):
    recruiter_id = uuid4()
    for action_type in ("autonomous_apply", "outreach_draft", "resume_tailoring"):
        await ai_supervision_service.record_ai_action(
            db_session,
            action_type=action_type,
            candidate_user_id=uuid4(),
            triggered_by_user_id=recruiter_id,
            summary=f"seed for {action_type}",
        )

    response = client.get(
        "/api/admin/ai-actions",
        params={"recruiter_id": str(recruiter_id)},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert body["has_more"] is False
    returned_action_types = {item["action_type"] for item in body["items"]}
    assert returned_action_types == {"autonomous_apply", "outreach_draft", "resume_tailoring"}
    assert len(body["items"]) == 3


# ---------------------------------------------------------------------------
# Filtering: individually and combined
# ---------------------------------------------------------------------------


async def test_filter_by_candidate_id(client, superuser, auth_headers, db_session):
    candidate_id = uuid4()
    other_candidate_id = uuid4()
    await ai_supervision_service.record_ai_action(
        db_session, action_type="outreach_draft", candidate_user_id=candidate_id
    )
    await ai_supervision_service.record_ai_action(
        db_session, action_type="outreach_draft", candidate_user_id=other_candidate_id
    )

    response = client.get(
        "/api/admin/ai-actions",
        params={"candidate_id": str(candidate_id)},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert len(body["items"]) == 1
    assert body["items"][0]["candidate_user_id"] == str(candidate_id)


async def test_filter_by_recruiter_id(client, superuser, auth_headers, db_session):
    recruiter_id = uuid4()
    other_recruiter_id = uuid4()
    await ai_supervision_service.record_ai_action(
        db_session,
        action_type="autonomous_apply",
        candidate_user_id=uuid4(),
        triggered_by_user_id=recruiter_id,
    )
    await ai_supervision_service.record_ai_action(
        db_session,
        action_type="autonomous_apply",
        candidate_user_id=uuid4(),
        triggered_by_user_id=other_recruiter_id,
    )

    response = client.get(
        "/api/admin/ai-actions",
        params={"recruiter_id": str(recruiter_id)},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert len(body["items"]) == 1
    assert body["items"][0]["triggered_by_user_id"] == str(recruiter_id)


async def test_filter_by_action_type(client, superuser, auth_headers, db_session):
    candidate_id = uuid4()
    await ai_supervision_service.record_ai_action(
        db_session, action_type="resume_tailoring", candidate_user_id=candidate_id
    )
    await ai_supervision_service.record_ai_action(
        db_session, action_type="outreach_draft", candidate_user_id=candidate_id
    )

    response = client.get(
        "/api/admin/ai-actions",
        params={"candidate_id": str(candidate_id), "action_type": "resume_tailoring"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert len(body["items"]) == 1
    assert body["items"][0]["action_type"] == "resume_tailoring"


async def test_filter_by_since_and_until(client, superuser, auth_headers, db_session):
    candidate_id = uuid4()
    now = datetime.now(UTC)

    old_row = AiActionAuditLog(
        action_type="outreach_draft",
        candidate_user_id=candidate_id,
        created_at=now - timedelta(days=10),
    )
    recent_row = AiActionAuditLog(
        action_type="outreach_draft",
        candidate_user_id=candidate_id,
        created_at=now - timedelta(minutes=5),
    )
    db_session.add_all([old_row, recent_row])
    await db_session.commit()

    response = client.get(
        "/api/admin/ai-actions",
        params={
            "candidate_id": str(candidate_id),
            "since": (now - timedelta(days=1)).isoformat(),
        },
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    returned_ids = {item["id"] for item in body["items"]}
    assert str(recent_row.id) in returned_ids
    assert str(old_row.id) not in returned_ids

    response = client.get(
        "/api/admin/ai-actions",
        params={
            "candidate_id": str(candidate_id),
            "until": (now - timedelta(days=1)).isoformat(),
        },
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    returned_ids = {item["id"] for item in body["items"]}
    assert str(old_row.id) in returned_ids
    assert str(recent_row.id) not in returned_ids


async def test_filter_combined_candidate_recruiter_and_action_type(
    client, superuser, auth_headers, db_session
):
    candidate_id = uuid4()
    recruiter_id = uuid4()

    matching_row = await ai_supervision_service.record_ai_action(
        db_session,
        action_type="autonomous_apply",
        candidate_user_id=candidate_id,
        triggered_by_user_id=recruiter_id,
    )
    # Same candidate + recruiter, different action_type -- must be excluded.
    await ai_supervision_service.record_ai_action(
        db_session,
        action_type="outreach_draft",
        candidate_user_id=candidate_id,
        triggered_by_user_id=recruiter_id,
    )
    # Same action_type + candidate, different recruiter -- must be excluded.
    await ai_supervision_service.record_ai_action(
        db_session,
        action_type="autonomous_apply",
        candidate_user_id=candidate_id,
        triggered_by_user_id=uuid4(),
    )

    response = client.get(
        "/api/admin/ai-actions",
        params={
            "candidate_id": str(candidate_id),
            "recruiter_id": str(recruiter_id),
            "action_type": "autonomous_apply",
        },
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(matching_row.id)


# ---------------------------------------------------------------------------
# Detail endpoint
# ---------------------------------------------------------------------------


async def test_get_ai_action_404_for_unknown_id(client, superuser, auth_headers):
    response = client.get(f"/api/admin/ai-actions/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


async def test_get_ai_action_returns_full_row_for_known_id(
    client, superuser, auth_headers, db_session
):
    candidate_id = uuid4()
    recruiter_id = uuid4()
    related_id = uuid4()
    row = await ai_supervision_service.record_ai_action(
        db_session,
        action_type="autonomous_apply",
        candidate_user_id=candidate_id,
        triggered_by_user_id=recruiter_id,
        related_id=related_id,
        summary="drill-down detail test",
    )

    response = client.get(f"/api/admin/ai-actions/{row.id}", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert body["id"] == str(row.id)
    assert body["action_type"] == "autonomous_apply"
    assert body["candidate_user_id"] == str(candidate_id)
    assert body["triggered_by_user_id"] == str(recruiter_id)
    assert body["related_id"] == str(related_id)
    assert body["summary"] == "drill-down detail test"
