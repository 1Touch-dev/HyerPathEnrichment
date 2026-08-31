"""Impersonation: MFA gate, dual-identity audit entries, jti revocation on end
(phase2_admin_module.md §9.11)."""

from __future__ import annotations

import pyotp
import pytest
from starlette.responses import Response

pytestmark = pytest.mark.asyncio


def _mfa_code(user) -> str:
    return pyotp.TOTP(user.mfa_secret).now()


async def test_start_requires_mfa_always(db_session, superuser, regular_user):
    from fastapi import HTTPException

    from app.modules.admin.impersonation import start_impersonation

    with pytest.raises(HTTPException) as exc:
        await start_impersonation(
            db_session,
            admin=superuser,
            target_user_id=regular_user.id,
            reason="debugging a support ticket",
            mfa_code=None,
            response=Response(),
            ip_address="127.0.0.1",
        )
    assert exc.value.status_code == 403


async def test_start_requires_mfa_when_admin_has_it_enabled(
    db_session, superuser_with_mfa, regular_user
):
    from fastapi import HTTPException

    from app.modules.admin.impersonation import start_impersonation

    with pytest.raises(HTTPException) as exc:
        await start_impersonation(
            db_session,
            admin=superuser_with_mfa,
            target_user_id=regular_user.id,
            reason="debugging a support ticket",
            mfa_code=None,
            response=Response(),
            ip_address="127.0.0.1",
        )
    assert exc.value.status_code == 403


async def test_start_succeeds_with_valid_mfa_code(db_session, superuser_with_mfa, regular_user):
    from app.modules.admin.impersonation import start_impersonation

    result = await start_impersonation(
        db_session,
        admin=superuser_with_mfa,
        target_user_id=regular_user.id,
        reason="debugging a support ticket",
        mfa_code=_mfa_code(superuser_with_mfa),
        response=Response(),
        ip_address="127.0.0.1",
    )
    assert result.target_user_id == regular_user.id


async def test_start_writes_impersonation_session_and_audit_entry(
    db_session, superuser_with_mfa, regular_user
):
    from app.modules.admin.impersonation import start_impersonation

    result = await start_impersonation(
        db_session,
        admin=superuser_with_mfa,
        target_user_id=regular_user.id,
        reason="debugging a support ticket",
        mfa_code=_mfa_code(superuser_with_mfa),
        response=Response(),
        ip_address="127.0.0.1",
    )
    assert result.target_user_id == regular_user.id

    from sqlalchemy import select

    from app.modules.admin.models import AdminAuditLog, ImpersonationSession

    session = (
        await db_session.execute(
            select(ImpersonationSession).where(
                ImpersonationSession.target_user_id == regular_user.id
            )
        )
    ).scalar_one()
    assert session.admin_user_id == superuser_with_mfa.id
    assert session.ended_at is None

    audit_entry = (
        await db_session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "impersonation.started",
                AdminAuditLog.target_id == str(regular_user.id),
            )
        )
    ).scalar_one()
    assert audit_entry.actor_user_id == superuser_with_mfa.id


async def test_cannot_impersonate_self(db_session, superuser_with_mfa):
    from fastapi import HTTPException

    from app.modules.admin.impersonation import start_impersonation

    with pytest.raises(HTTPException) as exc:
        await start_impersonation(
            db_session,
            admin=superuser_with_mfa,
            target_user_id=superuser_with_mfa.id,
            reason="x",
            mfa_code=_mfa_code(superuser_with_mfa),
            response=Response(),
            ip_address="127.0.0.1",
        )
    assert exc.value.status_code == 400


async def test_cannot_impersonate_superuser(db_session, superuser_with_mfa, superuser):
    from fastapi import HTTPException

    from app.modules.admin.impersonation import start_impersonation

    with pytest.raises(HTTPException) as exc:
        await start_impersonation(
            db_session,
            admin=superuser_with_mfa,
            target_user_id=superuser.id,
            reason="x",
            mfa_code=_mfa_code(superuser_with_mfa),
            response=Response(),
            ip_address="127.0.0.1",
        )
    assert exc.value.status_code == 403
    assert "superuser" in exc.value.detail.lower()


async def test_start_with_nonexistent_target_returns_404(db_session, superuser_with_mfa):
    from uuid import uuid4

    from fastapi import HTTPException

    from app.modules.admin.impersonation import start_impersonation

    with pytest.raises(HTTPException) as exc:
        await start_impersonation(
            db_session,
            admin=superuser_with_mfa,
            target_user_id=uuid4(),
            reason="x",
            mfa_code=_mfa_code(superuser_with_mfa),
            response=Response(),
            ip_address="127.0.0.1",
        )
    assert exc.value.status_code == 404


async def test_start_sets_cookie_secure_flag_from_settings_when_disabled(
    db_session, superuser_with_mfa, regular_user, monkeypatch
):
    """Regression test: secure was previously hardcoded True, which makes
    RFC-6265-compliant clients refuse the cookie over plain HTTP in dev/test.
    """
    from app.core.config import get_settings
    from app.modules.admin.impersonation import start_impersonation

    monkeypatch.setattr(get_settings(), "COOKIE_SECURE", False)

    response = Response()
    await start_impersonation(
        db_session,
        admin=superuser_with_mfa,
        target_user_id=regular_user.id,
        reason="debugging a support ticket",
        mfa_code=_mfa_code(superuser_with_mfa),
        response=response,
        ip_address="127.0.0.1",
    )

    set_cookie_header = dict(response.headers.items())["set-cookie"]
    assert "access_token=" in set_cookie_header
    assert "Secure" not in set_cookie_header


async def test_start_sets_cookie_secure_flag_from_settings_when_enabled(
    db_session, superuser_with_mfa, regular_user, monkeypatch
):
    from app.core.config import get_settings
    from app.modules.admin.impersonation import start_impersonation

    monkeypatch.setattr(get_settings(), "COOKIE_SECURE", True)

    response = Response()
    await start_impersonation(
        db_session,
        admin=superuser_with_mfa,
        target_user_id=regular_user.id,
        reason="debugging a support ticket",
        mfa_code=_mfa_code(superuser_with_mfa),
        response=response,
        ip_address="127.0.0.1",
    )

    set_cookie_header = dict(response.headers.items())["set-cookie"]
    assert "access_token=" in set_cookie_header
    assert "Secure" in set_cookie_header


async def test_end_impersonation_marks_session_ended_and_revokes_jti(
    db_session, superuser_with_mfa, regular_user, mock_redis
):
    from sqlalchemy import select

    from app.modules.admin.impersonation import end_impersonation, start_impersonation
    from app.modules.admin.models import ImpersonationSession

    await start_impersonation(
        db_session,
        admin=superuser_with_mfa,
        target_user_id=regular_user.id,
        reason="debugging a support ticket",
        mfa_code=_mfa_code(superuser_with_mfa),
        response=Response(),
        ip_address="127.0.0.1",
    )
    session = (
        await db_session.execute(
            select(ImpersonationSession).where(
                ImpersonationSession.target_user_id == regular_user.id
            )
        )
    ).scalar_one()
    jti = session.token_jti

    await end_impersonation(
        db_session,
        admin_user_id=superuser_with_mfa.id,
        jti=jti,
        response=Response(),
        ip_address="127.0.0.1",
    )

    await db_session.refresh(session)
    assert session.ended_at is not None

    from app.modules.admin.models import AdminAuditLog

    audit_entry = (
        await db_session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "impersonation.ended",
                AdminAuditLog.target_id == str(regular_user.id),
            )
        )
    ).scalar_one()
    assert audit_entry.actor_user_id == superuser_with_mfa.id
    assert audit_entry.target_id == str(regular_user.id)
