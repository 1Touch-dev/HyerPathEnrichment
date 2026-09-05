"""ADMIN-BE-003 transaction-boundary tests for staff-invite redemption."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.auth.models import User
from app.modules.admin.models import AdminAuditLog, Role
from app.modules.staff_invites import redemption, repository
from app.modules.staff_invites.models import StaffInvite

pytestmark = pytest.mark.asyncio


async def _issued_invite(db_session, superuser, *, email: str, key: str):
    return await repository.create_invite(
        db_session,
        email=email,
        role_name="recruiter",
        invited_by=superuser.id,
        request_id=f"{key}-request",
        idempotency_key=key,
    )


def _pending_user(email: str) -> User:
    return User(
        id=uuid4(),
        email=email,
        hashed_password="test-only-hash",
        first_name="Atomic",
        last_name="Invite",
        is_verified=False,
        is_active=True,
    )


async def _assert_redemption_rolled_back(
    db_session,
    *,
    user_id,
    invite_id,
) -> None:
    assert await db_session.get(User, user_id) is None
    invite = await db_session.get(StaffInvite, invite_id)
    assert invite is not None
    assert invite.accepted_at is None
    assert invite.accepted_by_user_id is None
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(
            AdminAuditLog.action == "user.role_changed",
            AdminAuditLog.target_id == str(user_id),
        )
    )
    assert audit_count == 0


async def test_redemption_rolls_back_when_role_staging_fails(
    db_session,
    superuser,
    monkeypatch,
):
    email = "redemption-stage-failure@example.com"
    (invite, _token) = await _issued_invite(
        db_session,
        superuser,
        email=email,
        key="redemption-stage-failure",
    )
    role = (await db_session.execute(select(Role).where(Role.name == "recruiter"))).scalar_one()
    user = _pending_user(email)
    user_id = user.id
    invite_id = invite.id

    monkeypatch.setattr(
        redemption.admin_service,
        "stage_role_assignment",
        AsyncMock(side_effect=RuntimeError("role staging failed")),
    )

    with pytest.raises(RuntimeError, match="role staging failed"):
        await redemption.persist_registration(
            db_session,
            user=user,
            invite=invite,
            invite_role=role,
            ip_address="127.0.0.1",
        )

    await _assert_redemption_rolled_back(
        db_session,
        user_id=user_id,
        invite_id=invite_id,
    )


async def test_redemption_rolls_back_staged_role_and_audit_failure(
    db_session,
    superuser,
    monkeypatch,
):
    email = "redemption-after-audit-failure@example.com"
    (invite, _token) = await _issued_invite(
        db_session,
        superuser,
        email=email,
        key="redemption-after-audit-failure",
    )
    role = (await db_session.execute(select(Role).where(Role.name == "recruiter"))).scalar_one()
    user = _pending_user(email)
    user_id = user.id
    invite_id = invite.id
    original_stage = redemption.admin_service.stage_role_assignment

    async def fail_after_staging(*args, **kwargs):
        await original_stage(*args, **kwargs)
        raise RuntimeError("failure after role and audit staging")

    monkeypatch.setattr(
        redemption.admin_service,
        "stage_role_assignment",
        fail_after_staging,
    )

    with pytest.raises(RuntimeError, match="failure after role and audit staging"):
        await redemption.persist_registration(
            db_session,
            user=user,
            invite=invite,
            invite_role=role,
            ip_address="127.0.0.1",
        )

    await _assert_redemption_rolled_back(
        db_session,
        user_id=user_id,
        invite_id=invite_id,
    )


async def test_redemption_rolls_back_when_final_commit_fails(
    db_session,
    superuser,
    monkeypatch,
):
    email = "redemption-commit-failure@example.com"
    (invite, _token) = await _issued_invite(
        db_session,
        superuser,
        email=email,
        key="redemption-commit-failure",
    )
    role = (await db_session.execute(select(Role).where(Role.name == "recruiter"))).scalar_one()
    user = _pending_user(email)
    user_id = user.id
    invite_id = invite.id

    with monkeypatch.context() as patch:
        patch.setattr(
            db_session,
            "commit",
            AsyncMock(side_effect=RuntimeError("final commit failed")),
        )
        with pytest.raises(RuntimeError, match="final commit failed"):
            await redemption.persist_registration(
                db_session,
                user=user,
                invite=invite,
                invite_role=role,
                ip_address="127.0.0.1",
            )

    await _assert_redemption_rolled_back(
        db_session,
        user_id=user_id,
        invite_id=invite_id,
    )
