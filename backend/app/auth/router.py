"""Authentication API routes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.auth.jwt_tokens import PyJWTError, decode_access_token, encode_access_token
from app.auth.logged_out_tokens import LoggedOutTokenService
from app.auth.models import AuthAuditLog, User
from app.auth.password import hash_password, verify_password
from app.auth.refresh_tokens import (
    create_refresh_token,
    detect_token_reuse,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    revoke_token_family,
    rotate_refresh_token,
    validate_refresh_token,
)
from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    ResendVerificationRequest,
    UserCreate,
    UserRead,
    VerifyEmailRequest,
)
from app.auth.verification import (
    generate_verification_token,
    resend_verification_email,
    send_verification_email,
    verify_email_token,
)
from app.core.config import get_settings
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_auth_rate_limit, enforce_auth_refresh_rate_limit
from app.infrastructure.redis import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


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


def create_access_token(user_id: str, email: str) -> tuple[str, str]:
    """
    Create JWT access token.

    Args:
        user_id: User UUID as string
        email: User email

    Returns:
        Tuple of (token, jti)
    """
    settings = get_settings()
    jti = f"{user_id}:{uuid4().hex}"
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "email": email,
        "jti": jti,
        "exp": datetime.now(UTC) + expires_delta,
        "iat": datetime.now(UTC),
    }

    token = encode_access_token(payload, settings.SECRET_KEY)
    return token, jti


async def log_auth_event(
    db: AsyncSession,
    event_type: str,
    success: bool,
    ip_address: str,
    user_agent: str | None = None,
    user_id: UUID | None = None,
    email_attempted: str | None = None,
    failure_reason: str | None = None,
) -> None:
    """Log authentication event to audit table."""
    audit_log = AuthAuditLog(
        user_id=user_id,
        event_type=event_type,
        success=success,
        ip_address=ip_address,
        user_agent=user_agent,
        email_attempted=email_attempted,
        failure_reason=failure_reason,
    )
    db.add(audit_log)
    await db.commit()


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Register new user account with email/password.

    Sends verification email after successful registration.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        is_verified=False,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate verification token
    verification_token = await generate_verification_token(db, user.id)

    # Send verification email
    await send_verification_email(user.email, user.first_name, verification_token)

    # Update verification sent timestamp
    user.verification_sent_at = datetime.now(UTC)
    await db.commit()

    # Log event
    await log_auth_event(
        db,
        "register",
        True,
        get_client_ip(request),
        request.headers.get("User-Agent"),
        user.id,
        user.email,
    )

    return MessageResponse(
        message="Registration successful. Please check your email to verify your account."
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def login(
    request: Request,
    credentials: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    """
    Login with email/password.

    Sets HttpOnly cookie with JWT access token.
    """
    # Find user
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    if not user or not user.hashed_password:
        await log_auth_event(
            db, "login", False, ip, user_agent, None, credentials.email, "Invalid credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Verify password
    if not verify_password(credentials.password, user.hashed_password):
        await log_auth_event(
            db, "login", False, ip, user_agent, user.id, credentials.email, "Invalid password"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Check if account is deleted
    if user.deleted_at is not None:
        await log_auth_event(
            db, "login", False, ip, user_agent, user.id, credentials.email, "Account deleted"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deleted",
        )

    # Check if account is active
    if not user.is_active:
        await log_auth_event(
            db, "login", False, ip, user_agent, user.id, credentials.email, "Account inactive"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Create access token
    access_token, _jti = create_access_token(str(user.id), user.email)

    # Create refresh token
    refresh_token_value, _ = await create_refresh_token(db, user.id)

    # Set HttpOnly cookies for both tokens
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN,
        path="/",  # Ensure cookie is available for all paths
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_value,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )

    # Log successful login
    await log_auth_event(db, "login", True, ip, user_agent, user.id, user.email)

    return LoginResponse(
        user=UserRead.model_validate(user),
        message="Login successful",
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Logout user by blacklisting token and clearing cookie.
    """
    settings = get_settings()

    # Get token from cookie and blacklist it
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            # Decode to get JTI and expiry
            payload = decode_access_token(access_token, settings.SECRET_KEY)
            jti = payload.get("jti")
            exp = payload.get("exp")

            if jti and exp:
                # Add to blacklist (dual Redis + PostgreSQL)
                redis_client = get_redis_client()
                blacklist_service = LoggedOutTokenService(redis_client)

                await blacklist_service.add_logout_token(
                    db=db,
                    user_id=current_user.id,
                    token_jti=jti,
                    expires_at=datetime.fromtimestamp(exp, tz=UTC),
                )
        except PyJWTError as e:
            logger.warning(f"Failed to decode token for blacklisting: {e}")

    # Clear cookie (must match path from set_cookie)
    response.delete_cookie(key="access_token", domain=settings.COOKIE_DOMAIN, path="/")

    # Revoke refresh token if present
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)

    # Clear refresh token cookie
    response.delete_cookie(key="refresh_token", domain=settings.COOKIE_DOMAIN, path="/")

    # Log logout
    await log_auth_event(
        db,
        "logout",
        True,
        get_client_ip(request),
        request.headers.get("User-Agent"),
        current_user.id,
        current_user.email,
    )

    return MessageResponse(message="Logged out successfully")


@router.post(
    "/refresh",
    response_model=LoginResponse,
    dependencies=[Depends(enforce_auth_refresh_rate_limit)],
)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    """
    Refresh access token using refresh token.

    Implements token rotation - issues new refresh token and invalidates old one.
    Detects token reuse and revokes entire token family for security.
    """
    settings = get_settings()
    ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    # Validate refresh token
    token_obj, user = await validate_refresh_token(db, refresh_token)

    if not token_obj or not user:
        await log_auth_event(
            db,
            "token_refresh",
            False,
            ip,
            user_agent,
            None,
            None,
            "Invalid or expired refresh token",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Detect token reuse (security breach)
    if await detect_token_reuse(db, token_obj):
        # Token was already used - revoke entire family
        await revoke_token_family(db, refresh_token, "Token reuse detected")

        # Log security event
        await log_auth_event(
            db,
            "token_reuse_detected",
            False,
            ip,
            user_agent,
            user.id,
            user.email,
            "Refresh token reuse - family revoked",
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token reuse detected. Please log in again.",
        )

    # Check if user is deleted
    if user.deleted_at is not None:
        await log_auth_event(
            db,
            "token_refresh",
            False,
            ip,
            user_agent,
            user.id,
            user.email,
            "Account deleted",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deleted",
        )

    # Check if user is active
    if not user.is_active:
        await log_auth_event(
            db,
            "token_refresh",
            False,
            ip,
            user_agent,
            user.id,
            user.email,
            "Account inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Rotate refresh token (mark old as used, create new)
    new_refresh_token_value, _ = await rotate_refresh_token(db, refresh_token, user.id)

    if not new_refresh_token_value:
        await log_auth_event(
            db,
            "token_refresh",
            False,
            ip,
            user_agent,
            user.id,
            user.email,
            "Token rotation failed",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rotate refresh token",
        )

    # Create new access token
    new_access_token, _jti = create_access_token(str(user.id), user.email)

    # Set new cookies
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token_value,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )

    # Log successful refresh
    await log_auth_event(
        db,
        "token_refresh",
        True,
        ip,
        user_agent,
        user.id,
        user.email,
    )

    return LoginResponse(
        user=UserRead.model_validate(user),
        message="Token refreshed successfully",
    )


@router.post("/delete-account", response_model=MessageResponse)
async def delete_account(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Soft delete user account (sets deleted_at timestamp).

    Also logs out by blacklisting token.
    """
    settings = get_settings()

    # Blacklist current token
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            payload = decode_access_token(access_token, settings.SECRET_KEY)
            jti = payload.get("jti")
            exp = payload.get("exp")

            if jti and exp:
                redis_client = get_redis_client()
                blacklist_service = LoggedOutTokenService(redis_client)

                await blacklist_service.add_logout_token(
                    db=db,
                    user_id=current_user.id,
                    token_jti=jti,
                    expires_at=datetime.fromtimestamp(exp, tz=UTC),
                )
        except PyJWTError as e:
            logger.warning(f"Failed to decode token for blacklisting: {e}")

    # Revoke all refresh sessions before soft-delete so stolen cookies cannot rotate.
    await revoke_all_refresh_tokens(db, current_user.id, reason="account deleted")

    # Erase user-owned product data (CVs, chat, outreach, sourced-lead PII).
    from app.compliance.account_erase import erase_user_owned_data

    await erase_user_owned_data(db, current_user.id)

    # Soft delete + clear MFA secret
    current_user.deleted_at = datetime.now(UTC)
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    await db.commit()

    # Clear cookies (must match path from set_cookie)
    response.delete_cookie(key="access_token", domain=settings.COOKIE_DOMAIN, path="/")
    response.delete_cookie(key="refresh_token", domain=settings.COOKIE_DOMAIN, path="/")

    # Log account deletion
    await log_auth_event(
        db,
        "delete_account",
        True,
        get_client_ip(request),
        request.headers.get("User-Agent"),
        current_user.id,
        current_user.email,
    )

    return MessageResponse(message="Account deleted successfully")


@router.get("/me", response_model=UserRead)
async def get_current_user(current_user: CurrentUser) -> UserRead:
    """Get current user profile."""
    return UserRead.model_validate(current_user)


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def verify_email(
    http_request: Request,
    db: AsyncSession = Depends(get_db_session),
    token: str | None = Query(None, description="Verification token from email link"),
    request: VerifyEmailRequest | None = None,
) -> MessageResponse:
    """
    Verify user email with token from email link.

    Accepts token either as:
    - Query parameter: POST /verify-email?token=xxx (standard for email links)
    - Request body: POST /verify-email with {"token": "xxx"}
    """
    # Get token from query param or request body
    verification_token = token or (request.token if request else None)

    if not verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is required (as query parameter or in request body)",
        )

    user = await verify_email_token(db, verification_token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # Log verification
    await log_auth_event(
        db,
        "email_verified",
        True,
        get_client_ip(http_request),
        http_request.headers.get("User-Agent"),
        user.id,
        user.email,
    )

    return MessageResponse(message="Email verified successfully. You can now log in.")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def resend_verification(
    request: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Resend verification email with 5-minute rate limit.

    Returns 429 Too Many Requests if called within 5 minutes of last send.
    """
    success, error_msg = await resend_verification_email(db, request.email)

    if not success:
        # Check if it's a rate limit error
        if error_msg and "Please wait" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg,
            )
        # Other errors (user not found, already verified)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg or "User not found or already verified",
        )

    return MessageResponse(message="Verification email sent. Please check your inbox.")
