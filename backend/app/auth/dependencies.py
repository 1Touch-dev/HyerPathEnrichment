"""FastAPI dependencies for authentication."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_tokens import PyJWTError, decode_access_token
from app.auth.logged_out_tokens import LoggedOutTokenService
from app.auth.models import User
from app.core.config import get_settings
from app.database.session import get_db_session
from app.infrastructure.redis import get_redis_client

_IMPERSONATION_ALLOWED_OPERATIONS = frozenset(
    {
        ("GET", "/auth/me"),
        ("GET", "/sessions"),
        ("GET", "/sessions/{session_id}"),
        ("GET", "/api/application-tracker/matches"),
        ("GET", "/api/billing/subscription"),
        ("GET", "/api/documents"),
        ("GET", "/api/documents/jobs/{job_id}"),
        ("GET", "/api/documents/{document_id}"),
        ("GET", "/api/documents/{document_id}/cv-data"),
        ("GET", "/api/documents/{document_id}/completeness"),
        ("GET", "/api/documents/{document_id}/feedback"),
        ("GET", "/api/documents/cv-chat/sessions/{session_id}"),
        ("GET", "/api/dsar/{dsar_id}"),
        ("GET", "/api/interviews/matches/{match_id}/schedule"),
        ("GET", "/api/interviews/matches/{match_id}/schedule.ics"),
        ("GET", "/api/job-matching/preferences"),
        ("GET", "/api/job-matching/matches"),
        ("GET", "/api/job-matching/events"),
        ("GET", "/api/matches/swipe-deck"),
        ("GET", "/api/outreach"),
        ("GET", "/api/outreach/company-tier"),
        ("GET", "/api/portfolio/profile"),
        ("GET", "/api/practice/audio/{recording_id}"),
        ("GET", "/api/recruiter-actions/pending"),
        ("GET", "/api/recruiter-actions/suggestions"),
        ("GET", "/api/resume-tailoring/{rq_job_id}"),
        ("GET", "/api/admin/mfa/status"),
        ("GET", "/api/admin/impersonation/status"),
        ("POST", "/api/admin/impersonation/end"),
    }
)


def get_client_ip(request: Request) -> str:
    """
    Extract real client IP from request headers.

    Checks X-Forwarded-For (behind proxy/LB), X-Real-IP, then falls back to direct client.
    """
    # Check X-Forwarded-For (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    # Fallback to direct client
    return request.client.host if request.client else "unknown"


async def get_current_user_from_cookie(
    request: Request,
    access_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Extract and validate JWT from HttpOnly cookie.

    Args:
        request: FastAPI request object
        access_token: JWT from cookie
        db: Database session

    Returns:
        Authenticated User object

    Raises:
        HTTPException: 401 if token invalid/expired/blacklisted
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()

    try:
        # Decode JWT (HS256 only)
        payload = decode_access_token(access_token, settings.SECRET_KEY)
        user_id_claim = payload.get("sub")
        jti_claim = payload.get("jti")
        impersonated_by_claim = payload.get("imp")
        if (
            not isinstance(user_id_claim, str)
            or not user_id_claim
            or not isinstance(jti_claim, str)
            or not jti_claim.strip()
            or jti_claim != jti_claim.strip()
            or len(jti_claim) > 128
        ):
            raise PyJWTError("Invalid token identity claims")
        user_id = UUID(user_id_claim)
        jti = jti_claim
        admin_user_id: UUID | None = None
        if impersonated_by_claim is not None:
            if not isinstance(impersonated_by_claim, str) or not impersonated_by_claim:
                raise PyJWTError("Invalid impersonation claim")
            admin_user_id = UUID(impersonated_by_claim)

        # Check if token is blacklisted (logout) with security alert
        redis_client = get_redis_client()
        blacklist_service = LoggedOutTokenService(redis_client)

        await blacklist_service.verify_token_not_logged_out(
            db=db,
            token_jti=jti,
            user_id=user_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )

    except (PyJWTError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Check if user is deleted
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deleted",
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if admin_user_id is not None:
        await _validate_impersonation_request(
            request,
            db=db,
            target=user,
            admin_user_id=admin_user_id,
            token_jti=jti,
        )

    # Admin Module (phase2_admin_module.md §8.4/§8.16): additive attribute for
    # code running outside FastAPI's Depends() injection (e.g. ASGI middleware)
    # that needs to know the acting user without re-decoding the JWT.
    request.state.user_id = user.id

    return user


async def _validate_impersonation_request(
    request: Request,
    *,
    db: AsyncSession,
    target: User,
    admin_user_id: UUID,
    token_jti: str,
) -> None:
    """Validate the authoritative impersonation grant on every impersonated request."""
    from app.modules.admin.models import ImpersonationSession
    from app.modules.admin.permissions import user_has_permission

    result = await db.execute(
        select(ImpersonationSession).where(
            ImpersonationSession.token_jti == token_jti,
            ImpersonationSession.admin_user_id == admin_user_id,
            ImpersonationSession.target_user_id == target.id,
        )
    )
    session = result.scalar_one_or_none()
    now = datetime.now(UTC)
    expires_at = session.expires_at if session is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    actor_result = await db.execute(select(User).where(User.id == admin_user_id))
    actor = actor_result.scalar_one_or_none()
    valid = (
        session is not None
        and session.scope == "view_only"
        and session.ended_at is None
        and session.revoked_at is None
        and expires_at is not None
        and expires_at > now
        and actor is not None
        and actor.is_active
        and actor.deleted_at is None
        and target.is_verified
        and not target.is_superuser
        and target.role_id is None
    )
    if (
        session is None
        or not valid
        or actor is None
        or not await user_has_permission(db, actor, "impersonation", "start")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Impersonation session is invalid or no longer active",
        )

    request.state.impersonated_by = actor.id
    request.state.impersonation_session_id = session.id
    request.state.token_jti = token_jti

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if (request.method, route_path) not in _IMPERSONATION_ALLOWED_OPERATIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Impersonated candidate sessions are read-only",
        )


async def require_verified_user(
    user: User = Depends(get_current_user_from_cookie),
) -> User:
    """
    Require user to be verified (email confirmed).

    Args:
        user: Current authenticated user

    Returns:
        Verified User object

    Raises:
        HTTPException: 403 if user not verified
    """
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Please check your email and verify your account.",
        )
    return user


# Aliases for common use cases
CurrentUser = Annotated[User, Depends(get_current_user_from_cookie)]
VerifiedUser = Annotated[User, Depends(require_verified_user)]
