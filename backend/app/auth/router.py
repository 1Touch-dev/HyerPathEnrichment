"""Authentication API routes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.auth.logged_out_tokens import LoggedOutTokenService
from app.auth.models import AuthAuditLog, User
from app.auth.password import hash_password, verify_password
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

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


async def log_auth_event(
    db: AsyncSession,
    event_type: str,
    success: bool,
    ip_address: str,
    user_agent: str | None = None,
    user_id: str | None = None,
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


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
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
        str(user.id),
        user.email,
    )

    return MessageResponse(
        message="Registration successful. Please check your email to verify your account."
    )


@router.post("/login", response_model=LoginResponse)
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
            db, "login", False, ip, user_agent, str(user.id), credentials.email, "Invalid password"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Check if account is deleted
    if user.deleted_at is not None:
        await log_auth_event(
            db, "login", False, ip, user_agent, str(user.id), credentials.email, "Account deleted"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deleted",
        )

    # Check if account is active
    if not user.is_active:
        await log_auth_event(
            db, "login", False, ip, user_agent, str(user.id), credentials.email, "Account inactive"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Create access token
    access_token, jti = create_access_token(str(user.id), user.email)

    # Set HttpOnly cookie
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN,
    )

    # Log successful login
    await log_auth_event(db, "login", True, ip, user_agent, str(user.id), user.email)

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
            payload = jwt.decode(
                access_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
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
        except JWTError as e:
            logger.warning(f"Failed to decode token for blacklisting: {e}")

    # Clear cookie
    response.delete_cookie(key="access_token", domain=settings.COOKIE_DOMAIN)

    # Log logout
    await log_auth_event(
        db,
        "logout",
        True,
        get_client_ip(request),
        request.headers.get("User-Agent"),
        str(current_user.id),
        current_user.email,
    )

    return MessageResponse(message="Logged out successfully")


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
            payload = jwt.decode(
                access_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
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
        except JWTError as e:
            logger.warning(f"Failed to decode token for blacklisting: {e}")

    # Soft delete
    current_user.deleted_at = datetime.now(UTC)
    await db.commit()

    # Clear cookie
    response.delete_cookie(key="access_token", domain=settings.COOKIE_DOMAIN)

    # Log account deletion
    await log_auth_event(
        db,
        "delete_account",
        True,
        get_client_ip(request),
        request.headers.get("User-Agent"),
        str(current_user.id),
        current_user.email,
    )

    return MessageResponse(message="Account deleted successfully")


@router.get("/me", response_model=UserRead)
async def get_current_user(current_user: CurrentUser) -> UserRead:
    """Get current user profile."""
    return UserRead.model_validate(current_user)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    http_request: Request,
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Verify user email with token from email link.
    """
    user = await verify_email_token(db, request.token)

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
        str(user.id),
        user.email,
    )

    return MessageResponse(message="Email verified successfully. You can now log in.")


@router.post("/resend-verification", response_model=MessageResponse)
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
