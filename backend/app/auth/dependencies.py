"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.logged_out_tokens import LoggedOutTokenService
from app.auth.models import User
from app.core.config import get_settings
from app.database.session import get_db_session
from app.infrastructure.redis import get_redis_client


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
        # Decode JWT
        payload = jwt.decode(
            access_token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")

        if user_id is None or jti is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Check if token is blacklisted (logout) with security alert
        redis_client = get_redis_client()
        blacklist_service = LoggedOutTokenService(redis_client)

        await blacklist_service.verify_token_not_logged_out(
            db=db,
            token_jti=jti,
            user_id=UUID(user_id),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
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

    return user


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
