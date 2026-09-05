"""Staff invite flow tests (machine-1-tenancy-core/05-org-invite-flow.md).

Covers the chunk's own verification checklist:
- uniform 404 rejection on GET /api/staff-invites/{token}, plus expiry fallback on
  POST /auth/register's fallback behavior
- duplicate-invite-to-same-email upsert idempotency (same `id`, not two rows)
- accepting a valid invite assigns the correct role (team_owner/recruiter are
  fully seeded via migration 047_seed_system_roles -- not the graceful-skip path)
- an invalid/garbage token falls back to normal signup: 201 Created with a
  non-empty `warning`, never a hard failure
- there is no seat/billing check anywhere in invite creation or acceptance
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.models import User
from app.modules.admin.models import Role
from app.modules.staff_invites import repository as staff_invites_repository
from app.modules.staff_invites.models import StaffInvite
from tests.envelope_helpers import assert_error, assert_success
from tests.migration_helpers import (
    drop_all_user_tables,
    postgres_test_url,
    upgrade_head,
)

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


def _issue_payload(email: str, actor) -> dict[str, str]:
    return {
        "email": email,
        "role_name": "recruiter",
        "confirmation_email": email,
        "mfa_code": pyotp.TOTP(actor.mfa_secret).now(),
    }


def _issue_headers(auth_headers, actor, key: str) -> dict[str, str]:
    return {**auth_headers(actor.id), "Idempotency-Key": key}


async def test_create_invite_requires_permission(client, regular_user, auth_headers):
    response = client.post(
        "/api/staff-invites",
        json={
            "email": "invitee@example.com",
            "role_name": "recruiter",
            "confirmation_email": "invitee@example.com",
            "mfa_code": "000000",
        },
        headers={**auth_headers(regular_user.id), "Idempotency-Key": "permission-denied"},
    )
    assert_error(response, 403)


async def test_create_invite_upsert_is_idempotent_by_id(client, superuser_with_mfa, auth_headers):
    """Calling create twice for the same still-pending, unexpired email must
    return the SAME invite row both times (assert on `id` equality), not two
    separate rows."""
    payload = _issue_payload("resend-me@example.com", superuser_with_mfa)

    first = client.post(
        "/api/staff-invites",
        json=payload,
        headers=_issue_headers(auth_headers, superuser_with_mfa, "resend-first"),
    )
    first_body = assert_success(first, status=201)

    second = client.post(
        "/api/staff-invites",
        json=payload,
        headers=_issue_headers(auth_headers, superuser_with_mfa, "resend-second"),
    )
    second_body = assert_success(second, status=201)

    assert first_body["id"] == second_body["id"]
    assert first_body["invite_token"]
    assert second_body["invite_token"] is None


async def test_get_invite_by_token_public_endpoint_no_auth_required(
    client, superuser_with_mfa, auth_headers, db_session
):
    created = client.post(
        "/api/staff-invites",
        json=_issue_payload("public-lookup@example.com", superuser_with_mfa),
        headers=_issue_headers(auth_headers, superuser_with_mfa, "public-lookup"),
    )
    created_body = assert_success(created, status=201)

    result = await db_session.execute(
        select(StaffInvite).where(StaffInvite.email == "public-lookup@example.com")
    )
    invite = result.scalar_one()
    plaintext_token = created_body["invite_token"]
    assert invite.token is None
    assert invite.token_digest == hashlib.sha256(plaintext_token.encode()).hexdigest()
    assert invite.role_id is not None

    response = client.get(f"/api/staff-invites/{plaintext_token}")
    lookup_body = assert_success(response)
    assert lookup_body["email"] == "public-lookup@example.com"
    assert lookup_body["role_name"] == "recruiter"


async def test_get_invite_by_token_404_for_unknown_token(client):
    response = client.get("/api/staff-invites/does-not-exist-token")
    body = assert_error(response, 404, "NOT_FOUND")
    assert body["error"]["message"] == "Invite unavailable"


async def test_get_invite_by_token_404_when_expired(client, superuser, db_session):
    from uuid import uuid4

    recruiter_role = (
        await db_session.execute(select(Role).where(Role.name == "recruiter"))
    ).scalar_one()
    token = "expired-token-abc123"

    invite = StaffInvite(
        id=uuid4(),
        email="expired@example.com",
        token=None,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        role_name="recruiter",
        role_id=recruiter_role.id,
        invited_by=superuser.id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(invite)
    await db_session.commit()

    response = client.get(f"/api/staff-invites/{token}")
    body = assert_error(response, 404, "NOT_FOUND")
    assert body["error"]["message"] == "Invite unavailable"


async def test_get_invite_by_token_404_when_already_accepted(client, superuser, db_session):
    from uuid import uuid4

    recruiter_role = (
        await db_session.execute(select(Role).where(Role.name == "recruiter"))
    ).scalar_one()
    token = "accepted-token-xyz789"
    invite = StaffInvite(
        id=uuid4(),
        email="accepted@example.com",
        token=None,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        role_name="recruiter",
        role_id=recruiter_role.id,
        invited_by=superuser.id,
        accepted_at=datetime.now(UTC),
    )
    db_session.add(invite)
    await db_session.commit()

    response = client.get(f"/api/staff-invites/{token}")
    body = assert_error(response, 404, "NOT_FOUND")
    assert body["error"]["message"] == "Invite unavailable"


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
    invite, plaintext_token = await staff_invites_repository.create_invite(
        db_session,
        email="new-recruiter@example.com",
        role_name="recruiter",
        invited_by=superuser.id,
        request_id="register-valid-invite",
        idempotency_key="register-valid-invite",
    )

    response = client.post(
        "/auth/register",
        json=_register_payload("new-recruiter@example.com", invite_token=plaintext_token),
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
    assert invite.accepted_by_user_id == user.id


async def test_legacy_plaintext_is_cleared_on_successful_redemption(client, superuser, db_session):
    from uuid import uuid4

    recruiter_role = (
        await db_session.execute(select(Role).where(Role.name == "recruiter"))
    ).scalar_one()
    token = "rolling-legacy-token"
    invite = StaffInvite(
        id=uuid4(),
        email="rolling-legacy@example.com",
        token=token,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        role_name="recruiter",
        role_id=recruiter_role.id,
        invited_by=superuser.id,
    )
    db_session.add(invite)
    await db_session.commit()

    response = client.post(
        "/auth/register",
        json=_register_payload("rolling-legacy@example.com", invite_token=token),
    )
    assert response.status_code == 201
    assert not response.json().get("warning")
    await db_session.refresh(invite)
    assert invite.accepted_at is not None
    assert invite.token is None
    assert invite.token_digest == hashlib.sha256(token.encode()).hexdigest()


async def test_explicit_plaintext_cleanup_bounds_legacy_fallback(superuser, db_session):
    from uuid import uuid4

    recruiter_role = (
        await db_session.execute(select(Role).where(Role.name == "recruiter"))
    ).scalar_one()
    now = datetime.now(UTC)
    active = StaffInvite(
        id=uuid4(),
        email="cleanup-active@example.com",
        token="cleanup-active-token",
        token_digest=None,
        role_name="recruiter",
        role_id=recruiter_role.id,
        invited_by=superuser.id,
        expires_at=now + timedelta(days=1),
    )
    expired = StaffInvite(
        id=uuid4(),
        email="cleanup-expired@example.com",
        token="cleanup-expired-token",
        token_digest=None,
        role_name="recruiter",
        role_id=recruiter_role.id,
        invited_by=superuser.id,
        expires_at=now - timedelta(days=1),
    )
    db_session.add_all([active, expired])
    await db_session.commit()

    cleared = await staff_invites_repository.clear_legacy_plaintext_tokens(db_session, now=now)
    assert cleared >= 1
    await db_session.refresh(active)
    await db_session.refresh(expired)
    assert active.token == "cleanup-active-token"
    assert expired.token is None
    assert expired.token_digest == hashlib.sha256(b"cleanup-expired-token").hexdigest()

    cleared = await staff_invites_repository.clear_legacy_plaintext_tokens(
        db_session,
        include_active=True,
        now=now,
    )
    assert cleared >= 1
    await db_session.refresh(active)
    assert active.token is None
    assert active.token_digest == hashlib.sha256(b"cleanup-active-token").hexdigest()


async def test_cleanup_script_requires_drain_and_smoke_acknowledgements(
    monkeypatch,
):
    from scripts.cleanup_staff_invite_plaintext import _parse_args

    monkeypatch.setattr(sys, "argv", ["cleanup_staff_invite_plaintext.py"])
    with pytest.raises(SystemExit):
        _parse_args()

    monkeypatch.setattr(
        sys,
        "argv",
        ["cleanup_staff_invite_plaintext.py", "--api-drain-acknowledged"],
    )
    with pytest.raises(SystemExit):
        _parse_args()

    monkeypatch.setattr(
        sys,
        "argv",
        ["cleanup_staff_invite_plaintext.py", "--new-code-smoke-passed"],
    )
    with pytest.raises(SystemExit):
        _parse_args()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cleanup_staff_invite_plaintext.py",
            "--include-active",
            "--api-drain-acknowledged",
            "--new-code-smoke-passed",
        ],
    )
    with pytest.raises(SystemExit):
        _parse_args()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cleanup_staff_invite_plaintext.py",
            "--include-active",
            "--api-drain-acknowledged",
            "--new-code-smoke-passed",
            "--schema-recovery-window-closed",
        ],
    )
    args = _parse_args()
    assert args.include_active is True
    assert args.api_drain_acknowledged is True
    assert args.new_code_smoke_passed is True
    assert args.schema_recovery_window_closed is True


async def test_expired_active_invite_is_revoked_before_reissue(
    client, superuser_with_mfa, auth_headers, db_session
):
    from uuid import uuid4

    recruiter_role = (
        await db_session.execute(select(Role).where(Role.name == "recruiter"))
    ).scalar_one()
    expired = StaffInvite(
        id=uuid4(),
        email="reissue@example.com",
        token="historical-expired-token",
        token_digest=hashlib.sha256(b"historical-expired-token").hexdigest(),
        role_name="recruiter",
        role_id=recruiter_role.id,
        invited_by=superuser_with_mfa.id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(expired)
    await db_session.commit()

    response = client.post(
        "/api/staff-invites",
        json=_issue_payload("REISSUE@example.com", superuser_with_mfa),
        headers=_issue_headers(auth_headers, superuser_with_mfa, "expired-reissue"),
    )
    body = assert_success(response, status=201)
    assert body["id"] != str(expired.id)
    assert body["invite_token"]

    await db_session.refresh(expired)
    assert expired.revoked_at is not None
    result = await db_session.execute(
        select(StaffInvite).where(
            StaffInvite.email.ilike("reissue@example.com"),
            StaffInvite.accepted_at.is_(None),
            StaffInvite.revoked_at.is_(None),
        )
    )
    assert len(result.scalars().all()) == 1


async def test_redeem_rejects_revoked_wrong_email_and_unsafe_role(client, superuser, db_session):
    recruiter_role = (
        await db_session.execute(select(Role).where(Role.name == "recruiter"))
    ).scalar_one()
    cases = [
        ("revoked@example.com", "recruiter", datetime.now(UTC), recruiter_role.id),
        ("unsafe@example.com", "admin", None, None),
    ]
    from uuid import uuid4

    for index, (email, role_name, revoked_at, role_id) in enumerate(cases):
        token = f"unsafe-invite-{index}"
        invite = StaffInvite(
            id=uuid4(),
            email=email,
            token=token,
            token_digest=hashlib.sha256(token.encode()).hexdigest(),
            role_name=role_name,
            role_id=role_id,
            invited_by=superuser.id,
            revoked_at=revoked_at,
        )
        db_session.add(invite)
        await db_session.commit()
        response = client.post(
            "/auth/register",
            json=_register_payload(email, invite_token=token),
        )
        assert response.status_code == 201
        assert response.json().get("warning")
        user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
        assert user.role_id is None

    invite, token = await staff_invites_repository.create_invite(
        db_session,
        email="bound@example.com",
        role_name="recruiter",
        invited_by=superuser.id,
        request_id="bound-email-invite",
        idempotency_key="bound-email-invite",
    )
    response = client.post(
        "/auth/register",
        json=_register_payload("different@example.com", invite_token=token),
    )
    assert response.status_code == 201
    assert response.json().get("warning")
    await db_session.refresh(invite)
    assert invite.accepted_at is None


async def test_no_seat_or_billing_check_on_invite_creation(
    client, superuser_with_mfa, auth_headers
):
    """There is no seat ceiling or billing/subscription lookup anywhere in this
    flow -- creating many invites must succeed regardless of how many staff
    already exist (this repo has no UserSubscription/seat-count model at all)."""
    for i in range(5):
        response = client.post(
            "/api/staff-invites",
            json=_issue_payload(f"bulk-invite-{i}@example.com", superuser_with_mfa),
            headers=_issue_headers(auth_headers, superuser_with_mfa, f"bulk-invite-{i}"),
        )
        assert_success(response, status=201)


@pytest.mark.postgres
async def test_concurrent_expired_reissue_has_one_deterministic_winner(
    monkeypatch,
):
    """Force both issuers past the expired-row read before either flushes.

    The database unique index chooses one insert; the losing transaction
    exercises repository.create_invite()'s IntegrityError recovery and returns
    the winner without receiving its one-time plaintext token.
    """
    url = postgres_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    drop_all_user_tables(url)
    upgrade_head(url)
    async_url = url
    if async_url.startswith("postgresql+psycopg://"):
        async_url = async_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    elif async_url.startswith("postgresql://"):
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(async_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as setup:
            actor = User(
                email="concurrent-reissue-actor@example.com",
                first_name="Concurrent",
                last_name="Actor",
                is_verified=True,
                is_active=True,
                is_superuser=True,
            )
            setup.add(actor)
            await setup.flush()
            actor_id = actor.id
            recruiter_role = (
                await setup.execute(select(Role).where(Role.name == "recruiter"))
            ).scalar_one()
            setup.add(
                StaffInvite(
                    email="concurrent-reissue@example.com",
                    token="concurrent-expired-token",
                    token_digest=hashlib.sha256(b"concurrent-expired-token").hexdigest(),
                    role_name="recruiter",
                    role_id=recruiter_role.id,
                    invited_by=actor_id,
                    expires_at=datetime.now(UTC) - timedelta(minutes=1),
                )
            )
            await setup.commit()

        original_flush = AsyncSession.flush
        both_ready = asyncio.Event()
        arrival_lock = asyncio.Lock()
        arrivals = 0

        async def coordinated_flush(self, *args, **kwargs):
            nonlocal arrivals
            revoking_expired = any(
                isinstance(obj, StaffInvite) and obj.revoked_at is not None for obj in self.dirty
            )
            if revoking_expired:
                async with arrival_lock:
                    arrivals += 1
                    if arrivals == 2:
                        both_ready.set()
                await asyncio.wait_for(both_ready.wait(), timeout=10)
            return await original_flush(self, *args, **kwargs)

        monkeypatch.setattr(AsyncSession, "flush", coordinated_flush)

        async def issue():
            async with sessions() as session:
                return await staff_invites_repository.create_invite(
                    session,
                    email="CONCURRENT-REISSUE@example.com",
                    role_name="recruiter",
                    invited_by=actor_id,
                    request_id=f"concurrent-reissue-{id(session)}",
                    idempotency_key=f"concurrent-reissue-{id(session)}",
                )

        results = await asyncio.gather(issue(), issue())
        assert results[0][0].id == results[1][0].id
        assert sorted(token is None for _, token in results) == [False, True]

        async with sessions() as verify:
            active_count = await verify.scalar(
                select(func.count())
                .select_from(StaffInvite)
                .where(
                    func.lower(StaffInvite.email) == "concurrent-reissue@example.com",
                    StaffInvite.accepted_at.is_(None),
                    StaffInvite.revoked_at.is_(None),
                )
            )
            assert active_count == 1
    finally:
        await engine.dispose()
