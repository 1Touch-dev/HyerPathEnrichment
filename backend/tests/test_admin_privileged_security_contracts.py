"""Focused security contracts for impersonation, MFA, and privileged audit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pyotp
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response

from app.auth.dependencies import get_current_user_from_cookie
from app.auth.jwt_tokens import create_user_access_token, encode_access_token
from app.auth.models import RefreshToken
from app.core.config import get_settings
from app.core.secret_box import open_secret
from app.modules.admin.models import AdminAuditLog, ImpersonationSession

pytestmark = pytest.mark.asyncio


def _request(
    method: str,
    path: str = "/api/documents",
    *,
    route_path: str | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "scheme": "https",
            "server": ("testserver", 443),
            "query_string": b"",
            "route": SimpleNamespace(path=route_path or path),
        }
    )


def _normal_token(user) -> str:
    return create_user_access_token(
        str(user.id),
        user.email,
        secret_key=get_settings().SECRET_KEY,
        expires_minutes=30,
    )[0]


async def _impersonation_token(db, actor, target, *, expires_at=None, revoked=False):
    jti = uuid4().hex
    expiry = expires_at or datetime.now(UTC) + timedelta(minutes=10)
    session = ImpersonationSession(
        admin_user_id=actor.id,
        target_user_id=target.id,
        token_jti=jti,
        reason="support diagnosis",
        scope="view_only",
        expires_at=expiry,
        revoked_at=datetime.now(UTC) if revoked else None,
        revoked_by=actor.id if revoked else None,
    )
    db.add(session)
    await db.commit()
    token = encode_access_token(
        {
            "sub": str(target.id),
            "imp": str(actor.id),
            "jti": jti,
            "exp": expiry,
        },
        get_settings().SECRET_KEY,
    )
    return token, session


async def test_normal_candidate_mutation_is_not_blocked(db_session, regular_user):
    user = await get_current_user_from_cookie(
        _request("PUT"),
        access_token=_normal_token(regular_user),
        db=db_session,
    )
    assert user.id == regular_user.id


async def test_active_impersonation_allows_reads_and_denies_mutations(
    db_session, superuser, regular_user
):
    token, session = await _impersonation_token(db_session, superuser, regular_user)

    request = _request("GET")
    user = await get_current_user_from_cookie(request, access_token=token, db=db_session)
    assert user.id == regular_user.id
    assert request.state.impersonated_by == superuser.id
    assert request.state.impersonation_session_id == session.id

    with pytest.raises(HTTPException) as exc:
        await get_current_user_from_cookie(
            _request("POST", "/api/documents/upload"),
            access_token=token,
            db=db_session,
        )
    assert exc.value.status_code == 403
    assert "read-only" in exc.value.detail


async def test_candidate_api_read_succeeds_but_mutation_is_denied(
    client, db_session, superuser, regular_user
):
    from app.auth.dependencies import require_verified_user
    from app.main import app

    token, _ = await _impersonation_token(db_session, superuser, regular_user)
    app.dependency_overrides.pop(get_current_user_from_cookie, None)
    app.dependency_overrides.pop(require_verified_user, None)
    client.cookies.set("access_token", token)

    read_response = client.get("/api/documents")
    mutation_response = client.delete("/api/job-matching/push-subscription")

    assert read_response.status_code == 200
    assert mutation_response.status_code == 403
    assert mutation_response.json()["error"]["message"].endswith("read-only")


async def test_unknown_get_operation_fails_closed(db_session, superuser, regular_user):
    token, _ = await _impersonation_token(db_session, superuser, regular_user)
    with pytest.raises(HTTPException) as exc:
        await get_current_user_from_cookie(
            _request("GET", "/api/future-stateful-get"),
            access_token=token,
            db=db_session,
        )
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    ("claim", "bad_value"),
    [
        pytest.param("sub", 123, id="sub-non-string"),
        pytest.param("sub", "not-a-uuid", id="sub-malformed"),
        pytest.param("sub", "", id="sub-empty"),
        pytest.param("jti", 123, id="jti-non-string"),
        pytest.param("jti", {"nested": "value"}, id="jti-object"),
        pytest.param("jti", "", id="jti-empty"),
        pytest.param("jti", " ", id="jti-whitespace"),
        pytest.param("jti", "x" * 129, id="jti-overlong"),
        pytest.param("imp", 123, id="imp-non-string"),
        pytest.param("imp", ["not", "a", "uuid"], id="imp-array"),
        pytest.param("imp", "not-a-uuid", id="imp-malformed"),
    ],
)
async def test_malformed_identity_claims_return_shared_401_before_infrastructure(
    client, db_session, regular_user, claim, bad_value
):
    from app.auth.dependencies import require_verified_user
    from app.auth.logged_out_tokens import LoggedOutTokenService
    from app.main import app

    payload = {
        "sub": str(regular_user.id),
        "jti": uuid4().hex,
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    payload[claim] = bad_value
    token = encode_access_token(
        payload,
        get_settings().SECRET_KEY,
    )
    app.dependency_overrides.pop(get_current_user_from_cookie, None)
    app.dependency_overrides.pop(require_verified_user, None)
    client.cookies.set("access_token", token)

    verify_blacklist = AsyncMock()
    with patch.object(
        LoggedOutTokenService,
        "verify_token_not_logged_out",
        new=verify_blacklist,
    ):
        response = client.get("/api/documents")

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Could not validate credentials",
            "details": None,
            "status_code": 401,
        },
        "meta": None,
    }
    verify_blacklist.assert_not_awaited()


async def test_impersonation_cannot_acquire_target_privileges(db_session, superuser, regular_user):
    from app.modules.admin.models import Role

    role = (await db_session.execute(select(Role).where(Role.name == "support"))).scalar_one()
    regular_user.role_id = role.id
    await db_session.commit()
    token, _ = await _impersonation_token(db_session, superuser, regular_user)

    with pytest.raises(HTTPException) as exc:
        await get_current_user_from_cookie(
            _request("GET"),
            access_token=token,
            db=db_session,
        )
    assert exc.value.status_code == 401


@pytest.mark.parametrize("state", ["revoked", "expired"])
async def test_stale_or_revoked_impersonation_fails_closed(
    db_session, superuser, regular_user, state
):
    token, _ = await _impersonation_token(
        db_session,
        superuser,
        regular_user,
        expires_at=(
            datetime.now(UTC) - timedelta(minutes=1)
            if state == "expired"
            else datetime.now(UTC) + timedelta(minutes=10)
        ),
        revoked=state == "revoked",
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_user_from_cookie(
            _request("GET"),
            access_token=token,
            db=db_session,
        )
    assert exc.value.status_code == 401


async def test_apply_redirect_is_denied_without_recording_click(
    client, db_session, superuser, regular_user
):
    from app.auth.dependencies import require_verified_user
    from app.main import app
    from app.modules.job_matching.models import JobMatch, JobPosting

    posting = JobPosting(
        dedup_key=f"impersonation-apply-{uuid4().hex}",
        title="Engineer",
        company="Example",
        location="Remote",
        remote=True,
        source="test",
        source_url="https://example.com/apply",
    )
    db_session.add(posting)
    await db_session.flush()
    match = JobMatch(
        user_id=regular_user.id,
        job_posting_id=posting.id,
        similarity_score=0.9,
        rule_score=0.8,
        overall_score=85.0,
        score_breakdown={},
    )
    db_session.add(match)
    await db_session.commit()
    match_id = match.id

    token, _ = await _impersonation_token(db_session, superuser, regular_user)
    app.dependency_overrides.pop(get_current_user_from_cookie, None)
    app.dependency_overrides.pop(require_verified_user, None)
    client.cookies.set("access_token", token)

    response = client.get(
        f"/api/job-matching/matches/{match_id}/apply-redirect",
        follow_redirects=False,
    )

    assert response.status_code == 403
    db_session.expire_all()
    persisted = (
        await db_session.execute(select(JobMatch).where(JobMatch.id == match_id))
    ).scalar_one()
    assert persisted.apply_clicked_at is None


async def test_status_uses_validated_session_not_newer_stale_session(
    db_session, superuser, regular_user
):
    from app.modules.admin.impersonation_router import get_impersonation_status

    _, validated = await _impersonation_token(db_session, superuser, regular_user)
    _, stale = await _impersonation_token(
        db_session,
        superuser,
        regular_user,
        expires_at=datetime.now(UTC) + timedelta(minutes=20),
        revoked=True,
    )
    stale.started_at = validated.started_at + timedelta(seconds=1)
    await db_session.commit()

    request = _request("GET", "/api/admin/impersonation/status")
    request.state.impersonated_by = superuser.id
    request.state.impersonation_session_id = validated.id
    result = await get_impersonation_status(
        request=request,
        current_user=regular_user,
        db=db_session,
    )

    assert result.is_impersonating is True
    assert result.expires_at == validated.expires_at
    assert result.expires_at != stale.expires_at


async def test_mfa_replacement_requires_current_code_and_revokes_refresh_sessions(
    db_session, superuser_with_mfa
):
    from app.modules.admin.mfa import enroll_mfa

    old_secret = open_secret(superuser_with_mfa.mfa_secret)
    refresh = RefreshToken(
        token=uuid4().hex,
        user_id=superuser_with_mfa.id,
        used=False,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(refresh)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await enroll_mfa(db_session, superuser_with_mfa)
    assert exc.value.status_code == 403

    replacement = await enroll_mfa(
        db_session,
        superuser_with_mfa,
        current_code=pyotp.TOTP(old_secret).now(),
    )
    assert replacement.secret != old_secret
    assert superuser_with_mfa.mfa_enabled is False
    await db_session.refresh(refresh)
    assert refresh.used is True


async def test_mfa_disable_reauthenticates_audits_and_never_records_secret(
    db_session, superuser_with_mfa
):
    from app.modules.admin.mfa import disable_mfa

    secret = open_secret(superuser_with_mfa.mfa_secret)
    with pytest.raises(HTTPException):
        await disable_mfa(db_session, superuser_with_mfa, "000000")
    assert superuser_with_mfa.mfa_enabled is True

    await disable_mfa(
        db_session,
        superuser_with_mfa,
        pyotp.TOTP(secret).now(),
    )
    audit = (
        await db_session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "mfa.disabled",
                AdminAuditLog.actor_user_id == superuser_with_mfa.id,
            )
        )
    ).scalar_one()
    assert audit.request_id
    assert audit.outcome == "success"
    assert secret not in repr(audit.before)
    assert secret not in repr(audit.after)


async def test_impersonation_end_audit_preserves_real_and_effective_identities(
    db_session, superuser_with_mfa, regular_user
):
    from app.modules.admin.impersonation import end_impersonation, start_impersonation

    refresh = RefreshToken(
        token=uuid4().hex,
        user_id=superuser_with_mfa.id,
        used=False,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(refresh)
    await db_session.commit()
    code = pyotp.TOTP(open_secret(superuser_with_mfa.mfa_secret)).now()
    await start_impersonation(
        db_session,
        admin=superuser_with_mfa,
        target_user_id=regular_user.id,
        reason="support diagnosis",
        mfa_code=code,
        response=Response(),
        ip_address="127.0.0.1",
    )
    await db_session.refresh(refresh)
    assert refresh.used is True
    session = (
        await db_session.execute(
            select(ImpersonationSession).where(
                ImpersonationSession.admin_user_id == superuser_with_mfa.id,
                ImpersonationSession.target_user_id == regular_user.id,
                ImpersonationSession.ended_at.is_(None),
            )
        )
    ).scalar_one()

    await end_impersonation(
        db_session,
        admin_user_id=superuser_with_mfa.id,
        jti=session.token_jti,
        response=Response(),
        ip_address="127.0.0.1",
    )
    audit = (
        await db_session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "impersonation.ended",
                AdminAuditLog.impersonation_session_id == session.id,
            )
        )
    ).scalar_one()
    assert audit.actor_user_id == regular_user.id
    assert audit.impersonated_by == superuser_with_mfa.id
    assert audit.target_id == str(regular_user.id)
    assert audit.request_id
    assert audit.outcome == "success"


async def test_impersonation_cookie_replaces_configured_domain_identity(
    db_session, superuser_with_mfa, regular_user, monkeypatch
):
    from http.cookies import SimpleCookie

    from app.auth.jwt_tokens import decode_access_token
    from app.modules.admin.impersonation import start_impersonation

    settings = get_settings()
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".example.com")
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    response = Response()
    await start_impersonation(
        db_session,
        admin=superuser_with_mfa,
        target_user_id=regular_user.id,
        reason="support diagnosis",
        mfa_code=pyotp.TOTP(open_secret(superuser_with_mfa.mfa_secret)).now(),
        response=response,
        ip_address="127.0.0.1",
    )

    access_headers = [
        value
        for value in response.headers.getlist("set-cookie")
        if value.startswith("access_token=")
    ]
    assert len(access_headers) == 1
    header = access_headers[0]
    assert "Domain=" in header
    assert "Path=/" in header
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=lax" in header

    cookies = SimpleCookie()
    cookies.load(header)
    assert cookies["access_token"]["domain"] == ".example.com"
    assert cookies["access_token"]["path"] == "/"
    payload = decode_access_token(cookies["access_token"].value, settings.SECRET_KEY)
    assert payload["sub"] == str(regular_user.id)
    assert payload["imp"] == str(superuser_with_mfa.id)


async def test_audit_failure_prevents_mfa_disable_commit(db_session, superuser_with_mfa):
    from app.modules.admin.mfa import disable_mfa

    secret = open_secret(superuser_with_mfa.mfa_secret)
    with (
        patch(
            "app.modules.admin.mfa.record_admin_action",
            new=AsyncMock(side_effect=RuntimeError("audit unavailable")),
        ),
        pytest.raises(RuntimeError, match="audit unavailable"),
    ):
        await disable_mfa(
            db_session,
            superuser_with_mfa,
            pyotp.TOTP(secret).now(),
        )

    await db_session.rollback()
    await db_session.refresh(superuser_with_mfa)
    assert superuser_with_mfa.mfa_enabled is True
    assert open_secret(superuser_with_mfa.mfa_secret) == secret


async def test_audit_failure_prevents_impersonation_session_commit(
    db_session, superuser_with_mfa, regular_user
):
    from app.modules.admin.impersonation import start_impersonation

    admin_id = superuser_with_mfa.id
    target_id = regular_user.id
    secret = open_secret(superuser_with_mfa.mfa_secret)
    with (
        patch(
            "app.modules.admin.impersonation.record_admin_action",
            new=AsyncMock(side_effect=RuntimeError("audit unavailable")),
        ),
        pytest.raises(RuntimeError, match="audit unavailable"),
    ):
        await start_impersonation(
            db_session,
            admin=superuser_with_mfa,
            target_user_id=regular_user.id,
            reason="support diagnosis",
            mfa_code=pyotp.TOTP(secret).now(),
            response=Response(),
            ip_address="127.0.0.1",
        )

    await db_session.rollback()
    sessions = (
        await db_session.execute(
            select(ImpersonationSession).where(
                ImpersonationSession.admin_user_id == admin_id,
                ImpersonationSession.target_user_id == target_id,
            )
        )
    ).scalars()
    assert list(sessions) == []
