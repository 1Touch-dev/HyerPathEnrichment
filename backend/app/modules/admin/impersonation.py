"""Support impersonation: a scoped JWT claim on the existing access_token
cookie, not a second auth system. See Decision 6. Sequenced last in the
build order (§9) — requires the audit log and MFA to already exist."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, Response, status
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.modules.admin import repository
from app.modules.admin.audit import record_admin_action
from app.modules.admin.mfa import verify_mfa_code
from app.modules.admin.models import ImpersonationSession
from app.modules.admin.schemas import ImpersonationStartResponse


async def start_impersonation(
    db: AsyncSession,
    *,
    admin: User,
    target_user_id: UUID,
    reason: str,
    mfa_code: str | None,
    response: Response,
    ip_address: str | None,
) -> ImpersonationStartResponse:
    if admin.mfa_enabled:
        if not mfa_code or not verify_mfa_code(admin, mfa_code):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Valid MFA code required to start an impersonation session",
            )

    target = await repository.get_user_by_id(db, target_user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target user not found")
    if target.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot impersonate yourself")

    settings = get_settings()
    jti = uuid4().hex
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.admin_impersonation_max_duration_minutes
    )

    payload = {
        "sub": str(target.id),
        "jti": jti,
        "imp": str(admin.id),
        "exp": expires_at,
    }
    # ✅ DIRECT (verified against backend/app/core/config.py and
    # backend/app/auth/router.py / dependencies.py, which already encode/decode
    # JWTs this way): settings.SECRET_KEY and settings.JWT_ALGORITHM match the
    # plan's assumed names exactly, no rename needed.
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        expires=int(expires_at.timestamp()),
    )

    session = ImpersonationSession(
        admin_user_id=admin.id,
        target_user_id=target.id,
        token_jti=jti,
        reason=reason,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    await record_admin_action(
        db,
        actor_user_id=admin.id,
        action="impersonation.started",
        target_type="user",
        target_id=str(target.id),
        after={"reason": reason, "expires_at": expires_at.isoformat()},
        ip_address=ip_address,
    )
    await db.commit()

    return ImpersonationStartResponse(target_user_id=target.id, expires_at=expires_at)


async def end_impersonation(
    db: AsyncSession, *, admin_user_id: UUID, jti: str, response: Response, ip_address: str | None
) -> None:
    from sqlalchemy import select

    result = await db.execute(
        select(ImpersonationSession).where(ImpersonationSession.token_jti == jti)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Impersonation session not found")

    session.ended_at = datetime.now(UTC)

    from app.auth.logged_out_tokens import LoggedOutTokenService
    from app.infrastructure.redis import get_redis_client

    # ✅ DIRECT (verified against backend/app/auth/logged_out_tokens.py, and how
    # backend/app/auth/router.py's own logout/delete-account flows call it):
    # there is no `blacklist_token(reason=...)` method as the plan assumed.
    # The real method is `add_logout_token(db, user_id, token_jti, expires_at)`
    # — no `reason` kwarg, and it needs the token's expiry (not a reason string)
    # to size the Redis TTL. `expires_at` is normalized to tz-aware UTC first:
    # SQLite reads datetimes back naive even though they were stored as UTC
    # (the same caveat `logged_out_tokens.py`'s own `_ensure_utc` helper guards
    # against), and `add_logout_token` would raise on a naive/aware subtraction
    # otherwise.
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    blacklist_service = LoggedOutTokenService(get_redis_client())
    await blacklist_service.add_logout_token(
        db=db, user_id=session.target_user_id, token_jti=jti, expires_at=expires_at
    )

    await record_admin_action(
        db,
        actor_user_id=admin_user_id,
        action="impersonation.ended",
        target_type="user",
        target_id=str(session.target_user_id),
        ip_address=ip_address,
    )
    await db.commit()
    response.delete_cookie("access_token")
