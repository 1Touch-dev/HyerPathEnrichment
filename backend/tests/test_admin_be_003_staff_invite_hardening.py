"""Focused ADMIN-BE-003 application-layer staff-invite security tests."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pyotp
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.auth import router as auth_router
from app.auth.models import User
from app.auth.schemas import UserCreate
from app.core import secret_box
from app.modules.admin import privileged_operations_repository
from app.modules.admin.models import AdminAuditLog, PrivilegedIdempotencyRecord, Role
from app.modules.staff_invites import repository
from app.modules.staff_invites.models import StaffInvite
from tests.envelope_helpers import assert_error, assert_success
from tests.migration_helpers import drop_all_user_tables, postgres_test_url, upgrade_head

pytestmark = pytest.mark.asyncio


def _register_payload(email: str, token: str) -> dict[str, str]:
    return {
        "email": email,
        "password": "SecurePass123!",
        "first_name": "Invite",
        "last_name": "Recipient",
        "invite_token": token,
    }


def _issue_payload(email: str, actor) -> dict[str, str]:
    return {
        "email": email,
        "role_name": "recruiter",
        "confirmation_email": email,
        "mfa_code": pyotp.TOTP(actor.mfa_secret).now(),
    }


def _issue_headers(auth_headers, actor, key: str) -> dict[str, str]:
    return {
        **auth_headers(actor.id),
        "Idempotency-Key": key,
        "X-Request-ID": f"request-{key}",
    }


async def _recruiter_role(db_session) -> Role:
    return (await db_session.execute(select(Role).where(Role.name == "recruiter"))).scalar_one()


async def test_admin_be_003_issuance_is_digest_only_and_transactionally_audited(
    client, superuser_with_mfa, auth_headers, db_session, caplog
):
    request_id = "admin-be-003-issuance"
    response = client.post(
        "/api/staff-invites",
        json=_issue_payload("Digest-Only@Example.com", superuser_with_mfa),
        headers={
            **_issue_headers(auth_headers, superuser_with_mfa, "digest-only"),
            "X-Request-ID": request_id,
        },
    )
    body = assert_success(response, status=201)
    raw_token = body["invite_token"]
    assert raw_token

    invite = (
        await db_session.execute(select(StaffInvite).where(StaffInvite.id == UUID(body["id"])))
    ).scalar_one()
    assert invite.email == "digest-only@example.com"
    assert invite.token is None
    assert invite.token_digest == hashlib.sha256(raw_token.encode()).hexdigest()
    assert invite.role_name == "recruiter"

    audit = (
        await db_session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "staff_invite.issued",
                AdminAuditLog.target_id == str(invite.id),
            )
        )
    ).scalar_one()
    assert audit.actor_user_id == superuser_with_mfa.id
    assert audit.request_id == request_id
    assert audit.outcome == "success"
    assert audit.captured_by == "explicit"
    assert raw_token not in caplog.text
    assert invite.email not in caplog.text
    assert raw_token not in repr(audit.after)
    assert invite.email not in repr(audit.after)


async def test_admin_be_003_rejects_unsafe_issuance_without_state_change(
    client, superuser_with_mfa, auth_headers, db_session
):
    payload = _issue_payload("unsafe-role@example.com", superuser_with_mfa)
    payload["role_name"] = "team_owner"
    response = client.post(
        "/api/staff-invites",
        json=payload,
        headers=_issue_headers(auth_headers, superuser_with_mfa, "unsafe-role"),
    )
    assert_error(response, 422)
    count = await db_session.scalar(
        select(func.count())
        .select_from(StaffInvite)
        .where(StaffInvite.email == "unsafe-role@example.com")
    )
    assert count == 0


async def test_admin_be_003_endpoint_requires_all_p3_controls(
    client, superuser, superuser_with_mfa, auth_headers
):
    email = "p3-controls@example.com"
    valid_payload = _issue_payload(email, superuser_with_mfa)

    missing_key = client.post(
        "/api/staff-invites",
        json=valid_payload,
        headers=auth_headers(superuser_with_mfa.id),
    )
    assert_error(missing_key, 422, "VALIDATION_ERROR")
    blank_key = client.post(
        "/api/staff-invites",
        json=valid_payload,
        headers={
            **auth_headers(superuser_with_mfa.id),
            "Idempotency-Key": "   ",
        },
    )
    assert_error(blank_key, 400, "VALIDATION_ERROR")

    wrong_confirmation = {
        **valid_payload,
        "confirmation_email": "different@example.com",
    }
    confirmation_response = client.post(
        "/api/staff-invites",
        json=wrong_confirmation,
        headers=_issue_headers(auth_headers, superuser_with_mfa, "wrong-confirmation"),
    )
    assert_error(confirmation_response, 400, "VALIDATION_ERROR")

    no_mfa_response = client.post(
        "/api/staff-invites",
        json={
            "email": email,
            "role_name": "recruiter",
            "confirmation_email": email,
            "mfa_code": "000000",
        },
        headers=_issue_headers(auth_headers, superuser, "no-mfa"),
    )
    assert_error(no_mfa_response, 403, "FORBIDDEN")

    bad_code = {**valid_payload, "mfa_code": "000000"}
    bad_code_response = client.post(
        "/api/staff-invites",
        json=bad_code,
        headers=_issue_headers(auth_headers, superuser_with_mfa, "bad-code"),
    )
    assert_error(bad_code_response, 403, "FORBIDDEN")


async def test_admin_be_003_service_requires_actor_and_request_id(superuser, db_session):
    with pytest.raises(ValueError, match="authenticated actor"):
        await repository.create_invite(
            db_session,
            email="missing-actor@example.com",
            role_name="recruiter",
            invited_by=None,  # type: ignore[arg-type]
            request_id="missing-actor",
            idempotency_key="missing-actor",
        )
    with pytest.raises(ValueError, match="request ID"):
        await repository.create_invite(
            db_session,
            email="missing-request@example.com",
            role_name="recruiter",
            invited_by=superuser.id,
            request_id="",
            idempotency_key="missing-request",
        )


async def test_admin_be_003_idempotent_replay_is_persisted_without_secrets(
    client, superuser_with_mfa, auth_headers, db_session
):
    payload = _issue_payload("persisted-replay@example.com", superuser_with_mfa)
    headers = _issue_headers(auth_headers, superuser_with_mfa, "persisted-replay")

    first = assert_success(
        client.post("/api/staff-invites", json=payload, headers=headers),
        status=201,
    )
    second = assert_success(
        client.post("/api/staff-invites", json=payload, headers=headers),
        status=201,
    )
    assert second["id"] == first["id"]
    assert first["invite_token"]
    assert second["invite_token"] == first["invite_token"]
    changed_payload = _issue_payload("changed-replay@example.com", superuser_with_mfa)
    changed = client.post(
        "/api/staff-invites",
        json=changed_payload,
        headers=headers,
    )
    assert_error(changed, 409, "IDEMPOTENCY_KEY_REUSED")

    record = (
        await db_session.execute(
            select(PrivilegedIdempotencyRecord).where(
                PrivilegedIdempotencyRecord.caller_user_id == superuser_with_mfa.id,
                PrivilegedIdempotencyRecord.operation == "staff_invite.issued",
                PrivilegedIdempotencyRecord.idempotency_key == "persisted-replay",
            )
        )
    ).scalar_one()
    assert record.completed_at is not None
    assert record.response_body["invite_id"] == first["id"]
    assert record.response_body["sealed_invite_token"] != first["invite_token"]
    serialized = repr(record.response_body)
    assert payload["email"] not in serialized
    assert first["invite_token"] not in serialized

    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(
            AdminAuditLog.action == "staff_invite.issued",
            AdminAuditLog.target_id == first["id"],
        )
    )
    assert audit_count == 1

    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    expired = client.post("/api/staff-invites", json=payload, headers=headers)
    assert_error(expired, 409, "IDEMPOTENCY_REPLAY_EXPIRED")


async def test_admin_be_003_sealed_replay_rejects_substitution_and_key_failure(
    client, superuser_with_mfa, auth_headers, db_session, monkeypatch
):
    payload = _issue_payload("sealed-failure@example.com", superuser_with_mfa)
    headers = _issue_headers(auth_headers, superuser_with_mfa, "sealed-failure")
    first = assert_success(
        client.post("/api/staff-invites", json=payload, headers=headers),
        status=201,
    )
    record = (
        await db_session.execute(
            select(PrivilegedIdempotencyRecord).where(
                PrivilegedIdempotencyRecord.caller_user_id == superuser_with_mfa.id,
                PrivilegedIdempotencyRecord.idempotency_key == "sealed-failure",
            )
        )
    ).scalar_one()
    original_response = dict(record.response_body)
    assert original_response["sealed_invite_token"] != first["invite_token"]

    for substituted_value in ("malformed-ciphertext", first["invite_token"]):
        record.response_body = {
            "invite_id": first["id"],
            "sealed_invite_token": substituted_value,
        }
        await db_session.commit()
        substitution = client.post("/api/staff-invites", json=payload, headers=headers)
        error = assert_error(substitution, 409, "IDEMPOTENCY_REPLAY_UNAVAILABLE")
        assert first["invite_token"] not in repr(error)

    mismatched_token = "validly-sealed-but-digest-mismatched-token"
    record.response_body = {
        "invite_id": first["id"],
        "sealed_invite_token": secret_box.seal_secret(mismatched_token),
    }
    await db_session.commit()
    digest_mismatch = client.post(
        "/api/staff-invites",
        json=payload,
        headers=headers,
    )
    error = assert_error(digest_mismatch, 409, "IDEMPOTENCY_REPLAY_UNAVAILABLE")
    assert first["invite_token"] not in repr(error)
    assert mismatched_token not in repr(error)

    record.response_body = original_response
    await db_session.commit()
    monkeypatch.setattr(
        secret_box,
        "get_settings",
        lambda: SimpleNamespace(SECRET_KEY="rotated-key-that-cannot-open-the-response"),
    )

    replay = client.post("/api/staff-invites", json=payload, headers=headers)
    error = assert_error(replay, 409, "IDEMPOTENCY_REPLAY_UNAVAILABLE")
    assert first["invite_token"] not in repr(error)


async def test_admin_be_003_public_errors_do_not_disclose_token_state(
    client, superuser, db_session
):
    role = await _recruiter_role(db_session)
    now = datetime.now(UTC)
    rows = [
        StaffInvite(
            id=uuid4(),
            email="expired-state@example.com",
            token=None,
            token_digest=hashlib.sha256(b"expired-state").hexdigest(),
            role_name="recruiter",
            role_id=role.id,
            invited_by=superuser.id,
            expires_at=now - timedelta(seconds=1),
        ),
        StaffInvite(
            id=uuid4(),
            email="revoked-state@example.com",
            token=None,
            token_digest=hashlib.sha256(b"revoked-state").hexdigest(),
            role_name="recruiter",
            role_id=role.id,
            invited_by=superuser.id,
            revoked_at=now,
        ),
        StaffInvite(
            id=uuid4(),
            email="accepted-state@example.com",
            token=None,
            token_digest=hashlib.sha256(b"accepted-state").hexdigest(),
            role_name="recruiter",
            role_id=role.id,
            invited_by=superuser.id,
            accepted_at=now,
        ),
        StaffInvite(
            id=uuid4(),
            email="unsafe-state@example.com",
            token=None,
            token_digest=hashlib.sha256(b"unsafe-state").hexdigest(),
            role_name="team_owner",
            role_id=None,
            invited_by=superuser.id,
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    states = ["unknown-state", "expired-state", "revoked-state", "accepted-state", "unsafe-state"]
    errors = [assert_error(client.get(f"/api/staff-invites/{token}"), 404) for token in states]
    assert {error["error"]["message"] for error in errors} == {"Invite unavailable"}


async def test_admin_be_003_legacy_fallback_is_only_safe_active_recruiter(superuser, db_session):
    role = await _recruiter_role(db_session)
    now = datetime.now(UTC)
    safe = StaffInvite(
        id=uuid4(),
        email="safe-legacy@example.com",
        token="safe-legacy-token",
        token_digest=None,
        role_name="recruiter",
        role_id=role.id,
        invited_by=superuser.id,
        expires_at=now + timedelta(hours=1),
    )
    digest_authoritative = StaffInvite(
        id=uuid4(),
        email="digest-authoritative@example.com",
        token="stale-plaintext-token",
        token_digest=hashlib.sha256(b"different-token").hexdigest(),
        role_name="recruiter",
        role_id=role.id,
        invited_by=superuser.id,
        expires_at=now + timedelta(hours=1),
    )
    unsafe = StaffInvite(
        id=uuid4(),
        email="unsafe-legacy@example.com",
        token="unsafe-legacy-token",
        token_digest=None,
        role_name="team_owner",
        role_id=None,
        invited_by=superuser.id,
        expires_at=now + timedelta(hours=1),
    )
    db_session.add_all([safe, digest_authoritative, unsafe])
    await db_session.commit()

    assert await repository.get_invite_by_token(db_session, safe.token) == safe
    assert await repository.get_invite_by_token(db_session, digest_authoritative.token) is None
    assert await repository.get_invite_by_token(db_session, unsafe.token) is None


async def test_admin_be_003_expired_reissue_and_replay_are_single_use(
    client, superuser_with_mfa, auth_headers, db_session
):
    role = await _recruiter_role(db_session)
    expired = StaffInvite(
        id=uuid4(),
        email="atomic-reissue@example.com",
        token=None,
        token_digest=hashlib.sha256(b"old-expired-token").hexdigest(),
        role_name="recruiter",
        role_id=role.id,
        invited_by=superuser_with_mfa.id,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db_session.add(expired)
    await db_session.commit()

    issued = assert_success(
        client.post(
            "/api/staff-invites",
            json=_issue_payload("ATOMIC-REISSUE@example.com", superuser_with_mfa),
            headers=_issue_headers(auth_headers, superuser_with_mfa, "atomic-reissue"),
        ),
        status=201,
    )
    await db_session.refresh(expired)
    assert expired.revoked_at is not None

    token = issued["invite_token"]
    first = client.post(
        "/auth/register",
        json=_register_payload("atomic-reissue@example.com", token),
    )
    assert first.status_code == 201

    replay = client.post(
        "/auth/register",
        json=_register_payload("replay-candidate@example.com", token),
    )
    assert replay.status_code == 201
    assert replay.json()["warning"]
    replay_user = (
        await db_session.execute(select(User).where(User.email == "replay-candidate@example.com"))
    ).scalar_one()
    assert replay_user.role_id is None


async def test_admin_be_003_unredeemable_active_invite_is_revoked_and_replaced(
    client, superuser_with_mfa, auth_headers, db_session
):
    role = await _recruiter_role(db_session)
    deleted_inviter = User(
        email="deleted-inviter@example.com",
        first_name="Deleted",
        last_name="Inviter",
        is_verified=True,
        is_active=False,
        deleted_at=datetime.now(UTC),
    )
    db_session.add(deleted_inviter)
    await db_session.flush()
    stale = StaffInvite(
        id=uuid4(),
        email="replace-unredeemable@example.com",
        token=None,
        token_digest=hashlib.sha256(b"unredeemable-token").hexdigest(),
        role_name="recruiter",
        role_id=role.id,
        invited_by=deleted_inviter.id,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(stale)
    await db_session.commit()

    issued = assert_success(
        client.post(
            "/api/staff-invites",
            json=_issue_payload("replace-unredeemable@example.com", superuser_with_mfa),
            headers=_issue_headers(
                auth_headers,
                superuser_with_mfa,
                "replace-unredeemable",
            ),
        ),
        status=201,
    )
    await db_session.refresh(stale)
    assert stale.revoked_at is not None
    assert issued["id"] != str(stale.id)
    assert issued["invite_token"]


@pytest.mark.parametrize("inviter_state", ["inactive", "soft_deleted"])
async def test_admin_be_003_digest_redemption_requires_current_active_inviter(
    client,
    superuser,
    db_session,
    inviter_state,
):
    role = await _recruiter_role(db_session)
    token = f"{inviter_state}-digest-invite-token"
    invite = StaffInvite(
        id=uuid4(),
        email=f"{inviter_state}-recipient@example.com",
        token=None,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        role_name="recruiter",
        role_id=role.id,
        invited_by=superuser.id,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    if inviter_state == "inactive":
        superuser.is_active = False
    else:
        superuser.deleted_at = datetime.now(UTC)
    db_session.add(invite)
    await db_session.commit()

    response = client.post(
        "/auth/register",
        json=_register_payload(invite.email, token),
    )
    body = response.json()
    assert response.status_code == 201
    assert body["warning"] == (
        "Your invite link is invalid or has expired; your account was created without staff access."
    )

    user = (await db_session.execute(select(User).where(User.email == invite.email))).scalar_one()
    assert user.role_id is None
    await db_session.refresh(invite)
    assert invite.accepted_at is None
    assert invite.accepted_by_user_id is None
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(
            AdminAuditLog.action == "user.role_changed",
            AdminAuditLog.target_id == str(user.id),
        )
    )
    assert audit_count == 0


def _postgres_async_url() -> str:
    url = postgres_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    drop_all_user_tables(url)
    upgrade_head(url)
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def _seed_postgres_actor(session) -> tuple[UUID, Role]:
    actor = User(
        email="admin-be-003-postgres-actor@example.com",
        first_name="Postgres",
        last_name="Actor",
        is_verified=True,
        is_active=True,
        is_superuser=True,
    )
    session.add(actor)
    await session.flush()
    role = (await session.execute(select(Role).where(Role.name == "recruiter"))).scalar_one()
    await session.commit()
    return actor.id, role


@pytest.mark.postgres
async def test_admin_be_003_postgres_concurrent_expired_reissue_is_atomic():
    engine = create_async_engine(_postgres_async_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as setup:
            actor_id, role = await _seed_postgres_actor(setup)
            expired = StaffInvite(
                id=uuid4(),
                email="race-invite@example.com",
                token="legacy-expired-race-token",
                token_digest=hashlib.sha256(b"legacy-expired-race-token").hexdigest(),
                role_name="recruiter",
                role_id=role.id,
                invited_by=actor_id,
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
            setup.add(expired)
            await setup.commit()
            expired_id = expired.id

        async def issue(index: int) -> tuple[StaffInvite, str | None]:
            async with sessions() as session:
                return await repository.create_invite(
                    session,
                    email="race-invite@example.com",
                    role_name="recruiter",
                    invited_by=actor_id,
                    request_id=f"race-request-{index}",
                    idempotency_key=f"race-key-{index}",
                )

        results = await asyncio.gather(*(issue(index) for index in range(4)))
        assert len({invite.id for invite, _ in results}) == 1
        assert sum(token is not None for _, token in results) == 1
        winner_token = next(token for _, token in results if token is not None)
        assert winner_token is not None

        async with sessions() as verify:
            active = (
                await verify.execute(
                    select(StaffInvite).where(
                        func.lower(StaffInvite.email) == "race-invite@example.com",
                        StaffInvite.accepted_at.is_(None),
                        StaffInvite.revoked_at.is_(None),
                    )
                )
            ).scalar_one()
            assert active.token is None
            assert active.token_digest == hashlib.sha256(winner_token.encode()).hexdigest()
            persisted_expired = await verify.get(StaffInvite, expired_id)
            assert persisted_expired is not None
            assert persisted_expired.revoked_at is not None
            audits = (
                (
                    await verify.execute(
                        select(AdminAuditLog).where(
                            AdminAuditLog.action == "staff_invite.issued",
                            AdminAuditLog.target_id == str(active.id),
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(audits) == 1
            assert audits[0].actor_user_id == actor_id
            assert audits[0].request_id in {
                "race-request-0",
                "race-request-1",
                "race-request-2",
                "race-request-3",
            }
            attempt_audits = (
                (
                    await verify.execute(
                        select(AdminAuditLog).where(
                            AdminAuditLog.target_id == str(active.id),
                            AdminAuditLog.action.in_(
                                {
                                    "staff_invite.issued",
                                    "staff_invite.conflict_winner",
                                }
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(attempt_audits) == 4
            assert {audit.request_id for audit in attempt_audits} == {
                "race-request-0",
                "race-request-1",
                "race-request-2",
                "race-request-3",
            }
            assert all(audit.captured_by == "explicit" for audit in attempt_audits)
    finally:
        await engine.dispose()


@pytest.mark.postgres
async def test_admin_be_003_postgres_idempotent_replay_has_one_audit():
    engine = create_async_engine(_postgres_async_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as setup:
            actor_id, _role = await _seed_postgres_actor(setup)

        async with sessions() as session:
            first, token = await repository.create_invite(
                session,
                email="postgres-replay@example.com",
                role_name="recruiter",
                invited_by=actor_id,
                request_id="postgres-replay-request",
                idempotency_key="postgres-replay-key",
            )
            replay, replay_token = await repository.create_invite(
                session,
                email="postgres-replay@example.com",
                role_name="recruiter",
                invited_by=actor_id,
                request_id="different-replay-request",
                idempotency_key="postgres-replay-key",
            )
            assert replay.id == first.id
            assert token is not None
            assert replay_token == token

        async with sessions() as verify:
            audit_count = await verify.scalar(
                select(func.count())
                .select_from(AdminAuditLog)
                .where(
                    AdminAuditLog.action == "staff_invite.issued",
                    AdminAuditLog.target_id == str(first.id),
                )
            )
            assert audit_count == 1
            replay_audit = (
                await verify.execute(
                    select(AdminAuditLog).where(
                        AdminAuditLog.action == "staff_invite.replayed",
                        AdminAuditLog.target_id == str(first.id),
                    )
                )
            ).scalar_one()
            assert replay_audit.request_id == "different-replay-request"
            assert replay_audit.actor_user_id == actor_id
            assert replay_audit.captured_by == "explicit"
            record = (
                await verify.execute(
                    select(PrivilegedIdempotencyRecord).where(
                        PrivilegedIdempotencyRecord.caller_user_id == actor_id,
                        PrivilegedIdempotencyRecord.operation == "staff_invite.issued",
                        PrivilegedIdempotencyRecord.idempotency_key == "postgres-replay-key",
                    )
                )
            ).scalar_one()
            assert record.response_body["invite_id"] == str(first.id)
            assert record.response_body["sealed_invite_token"] != token
            assert token not in repr(record.response_body)
            assert "postgres-replay@example.com" not in repr(record.response_body)
    finally:
        await engine.dispose()


@pytest.mark.postgres
async def test_admin_be_003_postgres_legacy_redemption_loses_to_inviter_deactivation(
    monkeypatch,
):
    engine = create_async_engine(_postgres_async_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    email = "legacy-deactivation-race@example.com"
    token = "legacy-deactivation-race-token"
    try:
        async with sessions() as setup:
            actor_id, role = await _seed_postgres_actor(setup)
            invite = StaffInvite(
                id=uuid4(),
                email=email,
                token=token,
                token_digest=None,
                role_name="recruiter",
                role_id=role.id,
                invited_by=actor_id,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
            setup.add(invite)
            await setup.commit()
            invite_id = invite.id

        monkeypatch.setattr(
            auth_router,
            "send_verification_email",
            AsyncMock(return_value=None),
        )

        async with sessions() as deactivation_session:
            locked_actor_id = await deactivation_session.scalar(
                select(User.id).where(User.id == actor_id).with_for_update()
            )
            assert locked_actor_id is not None
            locked_actor = await deactivation_session.get(User, locked_actor_id)
            assert locked_actor is not None
            locked_actor.is_active = False
            await deactivation_session.flush()

            async with sessions() as redemption_session:
                inviter_lock_attempted = asyncio.Event()
                original_scalar = redemption_session.scalar

                async def observe_locked_inviter_scalar(statement, *args, **kwargs):
                    entities = {
                        description.get("entity") for description in statement.column_descriptions
                    }
                    if getattr(statement, "_for_update_arg", None) is not None and User in entities:
                        inviter_lock_attempted.set()
                    return await original_scalar(statement, *args, **kwargs)

                monkeypatch.setattr(
                    redemption_session,
                    "scalar",
                    observe_locked_inviter_scalar,
                )
                request = Request(
                    {
                        "type": "http",
                        "method": "POST",
                        "path": "/auth/register",
                        "headers": [],
                        "client": ("127.0.0.1", 5000),
                    }
                )
                payload = UserCreate(**_register_payload(email, token))
                redemption_task = asyncio.create_task(
                    auth_router.register(request, payload, redemption_session)
                )

                try:
                    await asyncio.wait_for(inviter_lock_attempted.wait(), timeout=10)
                    assert not redemption_task.done()
                    await asyncio.wait_for(deactivation_session.commit(), timeout=10)
                    response = await asyncio.wait_for(
                        asyncio.shield(redemption_task),
                        timeout=10,
                    )
                except BaseException:
                    if not redemption_task.done():
                        redemption_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await asyncio.wait_for(redemption_task, timeout=10)
                    try:
                        await asyncio.wait_for(redemption_session.rollback(), timeout=10)
                    finally:
                        await asyncio.wait_for(deactivation_session.rollback(), timeout=10)
                    raise

        assert response.warning == (
            "Your invite link is invalid or has expired; "
            "your account was created without staff access."
        )

        async with sessions() as verify:
            candidate = (await verify.execute(select(User).where(User.email == email))).scalar_one()
            assert candidate.role_id is None
            inviter = await verify.get(User, actor_id)
            assert inviter is not None
            assert inviter.is_active is False

            persisted_invite = await verify.get(StaffInvite, invite_id)
            assert persisted_invite is not None
            assert persisted_invite.accepted_at is None
            assert persisted_invite.accepted_by_user_id is None
            assert persisted_invite.token == token

            role_audit_count = await verify.scalar(
                select(func.count())
                .select_from(AdminAuditLog)
                .where(
                    AdminAuditLog.action == "user.role_changed",
                    AdminAuditLog.target_id == str(candidate.id),
                )
            )
            assert role_audit_count == 0
    finally:
        await engine.dispose()


@pytest.mark.postgres
async def test_admin_be_003_postgres_concurrent_redemption_has_one_privileged_winner(
    monkeypatch,
):
    engine = create_async_engine(_postgres_async_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    email = "postgres-redemption-race@example.com"
    try:
        async with sessions() as setup:
            actor_id, role = await _seed_postgres_actor(setup)
            invite, token = await repository.create_invite(
                setup,
                email=email,
                role_name="recruiter",
                invited_by=actor_id,
                request_id="postgres-redemption-race-issuance",
                idempotency_key="postgres-redemption-race-issuance",
            )
            assert token is not None
            invite_id = invite.id

        monkeypatch.setattr(
            auth_router,
            "send_verification_email",
            AsyncMock(return_value=None),
        )
        original_lookup = repository.get_invite_by_token
        lookup_barrier = asyncio.Event()
        lookup_count = 0
        lookup_count_lock = asyncio.Lock()

        async def synchronized_lookup(*args, **kwargs):
            nonlocal lookup_count
            async with lookup_count_lock:
                lookup_count += 1
                if lookup_count == 2:
                    lookup_barrier.set()
            await lookup_barrier.wait()
            return await original_lookup(*args, **kwargs)

        monkeypatch.setattr(repository, "get_invite_by_token", synchronized_lookup)

        async def redeem(index: int) -> int:
            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/auth/register",
                    "headers": [],
                    "client": (f"127.0.0.{index + 1}", 5000 + index),
                }
            )
            payload = UserCreate(**_register_payload(email, token))
            async with sessions() as session:
                try:
                    await auth_router.register(request, payload, session)
                except HTTPException as exc:
                    await session.rollback()
                    return exc.status_code
                return 201

        statuses = await asyncio.gather(redeem(0), redeem(1))
        assert sorted(statuses) == [201, 400]

        async with sessions() as verify:
            users = (await verify.execute(select(User).where(User.email == email))).scalars().all()
            assert len(users) == 1
            winner = users[0]
            assert winner.role_id == role.id

            persisted_invite = await verify.get(StaffInvite, invite_id)
            assert persisted_invite is not None
            assert persisted_invite.accepted_at is not None
            assert persisted_invite.accepted_by_user_id == winner.id
            assert persisted_invite.token is None

            role_audits = (
                (
                    await verify.execute(
                        select(AdminAuditLog).where(
                            AdminAuditLog.action == "user.role_changed",
                            AdminAuditLog.target_id == str(winner.id),
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(role_audits) == 1
            assert role_audits[0].actor_user_id == actor_id
            assert role_audits[0].captured_by == "explicit"
            assert role_audits[0].outcome == "success"

            pending_invites = await verify.scalar(
                select(func.count())
                .select_from(StaffInvite)
                .where(
                    StaffInvite.email == email,
                    StaffInvite.accepted_at.is_(None),
                    StaffInvite.revoked_at.is_(None),
                )
            )
            assert pending_invites == 0
    finally:
        await engine.dispose()


@pytest.mark.postgres
async def test_admin_be_003_postgres_injected_failure_rolls_back_everything(
    monkeypatch,
):
    engine = create_async_engine(_postgres_async_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as setup:
            actor_id, role = await _seed_postgres_actor(setup)
            expired = StaffInvite(
                id=uuid4(),
                email="rollback-injected@example.com",
                token=None,
                token_digest=hashlib.sha256(b"rollback-expired-token").hexdigest(),
                role_name="recruiter",
                role_id=role.id,
                invited_by=actor_id,
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
            setup.add(expired)
            await setup.commit()
            expired_id = expired.id

        async def fail_completion(*args, **kwargs):
            raise RuntimeError("injected idempotency completion failure")

        monkeypatch.setattr(
            privileged_operations_repository,
            "complete_idempotency_record",
            fail_completion,
        )
        async with sessions() as session:
            with pytest.raises(
                RuntimeError,
                match="injected idempotency completion failure",
            ):
                await repository.create_invite(
                    session,
                    email="rollback-injected@example.com",
                    role_name="recruiter",
                    invited_by=actor_id,
                    request_id="rollback-injected-request",
                    idempotency_key="rollback-injected-key",
                )

        async with sessions() as verify:
            invite_count = await verify.scalar(
                select(func.count())
                .select_from(StaffInvite)
                .where(StaffInvite.email == "rollback-injected@example.com")
            )
            restored_expired = await verify.get(StaffInvite, expired_id)
            audit_count = await verify.scalar(
                select(func.count())
                .select_from(AdminAuditLog)
                .where(AdminAuditLog.action == "staff_invite.issued")
            )
            idempotency_count = await verify.scalar(
                select(func.count())
                .select_from(PrivilegedIdempotencyRecord)
                .where(PrivilegedIdempotencyRecord.idempotency_key == "rollback-injected-key")
            )
            assert invite_count == 1
            assert restored_expired is not None
            assert restored_expired.revoked_at is None
            assert audit_count == 0
            assert idempotency_count == 0
    finally:
        await engine.dispose()
