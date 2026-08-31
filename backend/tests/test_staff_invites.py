"""Staff invite flow tests (machine-1-tenancy-core/05-org-invite-flow.md).

Covers the chunk's own verification checklist:
- token expiry rejection (404/410) on both GET /api/staff-invites/{token} and
  POST /auth/register's fallback behavior
- duplicate-invite-to-same-email upsert idempotency (same `id`, not two rows)
- accepting a valid invite assigns the correct role (team_owner/recruiter are
  fully seeded via migration 047_seed_system_roles -- not the graceful-skip path)
- an invalid/garbage token falls back to normal signup: 201 Created with a
  non-empty `warning`, never a hard failure
- there is no seat/billing check anywhere in invite creation or acceptance
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.auth.models import User
from app.modules.admin.models import Role
from app.modules.staff_invites import repository as staff_invites_repository
from app.modules.staff_invites.models import StaffInvite
from tests.envelope_helpers import assert_error, assert_success

pytestmark = pytest.mark.asyncio


def _register_payload(email: str, invite_token: str | None = None) -> dict:
    payload = {
        "email": email,
        "password": "SecurePass123!",
        "first_name": "New",
        "last_name": "Staffer",
    }
    if invite_token is not None:
        payload["invite_token"] = invite_token
    return payload


async def test_create_invite_requires_permission(client, regular_user, auth_headers):
    response = client.post(
        "/api/staff-invites",
        json={"email": "invitee@example.com", "role_name": "recruiter"},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)


async def test_create_invite_upsert_is_idempotent_by_id(client, superuser, auth_headers):
    """Calling create twice for the same still-pending, unexpired email must
    return the SAME invite row both times (assert on `id` equality), not two
    separate rows."""
    payload = {"email": "resend-me@example.com", "role_name": "recruiter"}

    first = client.post("/api/staff-invites", json=payload, headers=auth_headers(superuser.id))
    first_body = assert_success(first, status=201)

    second = client.post("/api/staff-invites", json=payload, headers=auth_headers(superuser.id))
    second_body = assert_success(second, status=201)

    assert first_body["id"] == second_body["id"]


async def test_get_invite_by_token_public_endpoint_no_auth_required(
    client, superuser, auth_headers, db_session
):
    created = client.post(
        "/api/staff-invites",
        json={"email": "public-lookup@example.com", "role_name": "recruiter"},
        headers=auth_headers(superuser.id),
    )
    assert_success(created, status=201)

    result = await db_session.execute(
        select(StaffInvite).where(StaffInvite.email == "public-lookup@example.com")
    )
    invite = result.scalar_one()

    response = client.get(f"/api/staff-invites/{invite.token}")
    lookup_body = assert_success(response)
    assert lookup_body["email"] == "public-lookup@example.com"
    assert lookup_body["role_name"] == "recruiter"


async def test_get_invite_by_token_404_for_unknown_token(client):
    response = client.get("/api/staff-invites/does-not-exist-token")
    assert_error(response, 404)


async def test_get_invite_by_token_410_when_expired(client, db_session):
    from uuid import uuid4

    invite = StaffInvite(
        id=uuid4(),
        email="expired@example.com",
        token="expired-token-abc123",
        role_name="recruiter",
        invited_by=None,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(invite)
    await db_session.commit()

    response = client.get(f"/api/staff-invites/{invite.token}")
    assert_error(response, 410)


async def test_get_invite_by_token_410_when_already_accepted(client, db_session):
    from uuid import uuid4

    invite = StaffInvite(
        id=uuid4(),
        email="accepted@example.com",
        token="accepted-token-xyz789",
        role_name="recruiter",
        invited_by=None,
        accepted_at=datetime.now(UTC),
    )
    db_session.add(invite)
    await db_session.commit()

    response = client.get(f"/api/staff-invites/{invite.token}")
    assert_error(response, 410)


async def test_register_with_invalid_token_falls_back_with_warning(client):
    """An invalid/garbage invite_token never hard-fails registration -- it falls
    back to a normal candidate signup, 201 Created, with a non-empty `warning`."""
    response = client.post(
        "/auth/register",
        json=_register_payload("garbage-token-user@example.com", invite_token="not-a-real-token"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body.get("warning")


async def test_register_with_expired_token_falls_back_with_warning(client, db_session):
    from uuid import uuid4

    invite = StaffInvite(
        id=uuid4(),
        email="expired-signup@example.com",
        token="expired-signup-token",
        role_name="recruiter",
        invited_by=None,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(invite)
    await db_session.commit()

    response = client.post(
        "/auth/register",
        json=_register_payload("expired-signup@example.com", invite_token=invite.token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body.get("warning")

    # The account was still created despite the dead invite link.
    result = await db_session.execute(
        select(User).where(User.email == "expired-signup@example.com")
    )
    assert result.scalar_one_or_none() is not None


async def test_register_without_invite_token_has_no_warning(client):
    """Regression: registering with no `invite_token` at all must not surface a
    warning -- byte-shape aside, `warning` must stay falsy for ordinary signups."""
    response = client.post("/auth/register", json=_register_payload("plain-signup@example.com"))
    assert response.status_code == 201
    body = response.json()
    assert not body.get("warning")


async def test_register_with_valid_invite_assigns_role(client, superuser, db_session):
    """Accepting a valid invite assigns the correct role. team_owner/recruiter
    are fully seeded (migration 047_seed_system_roles), so this exercises the
    real role-assignment path, not the graceful-skip fallback."""
    invite = await staff_invites_repository.create_invite(
        db_session,
        email="new-recruiter@example.com",
        role_name="recruiter",
        invited_by=superuser.id,
    )

    response = client.post(
        "/auth/register",
        json=_register_payload("new-recruiter@example.com", invite_token=invite.token),
    )
    assert response.status_code == 201
    body = response.json()
    assert not body.get("warning")

    result = await db_session.execute(select(User).where(User.email == "new-recruiter@example.com"))
    user = result.scalar_one()

    role_result = await db_session.execute(select(Role).where(Role.name == "recruiter"))
    recruiter_role = role_result.scalar_one()
    assert user.role_id == recruiter_role.id

    await db_session.refresh(invite)
    assert invite.accepted_at is not None


async def test_no_seat_or_billing_check_on_invite_creation(client, superuser, auth_headers):
    """There is no seat ceiling or billing/subscription lookup anywhere in this
    flow -- creating many invites must succeed regardless of how many staff
    already exist (this repo has no UserSubscription/seat-count model at all)."""
    for i in range(5):
        response = client.post(
            "/api/staff-invites",
            json={"email": f"bulk-invite-{i}@example.com", "role_name": "recruiter"},
            headers=auth_headers(superuser.id),
        )
        assert_success(response, status=201)
