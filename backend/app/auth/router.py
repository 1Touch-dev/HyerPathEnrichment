"""Authentication API routes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.auth.jwt_tokens import PyJWTError, decode_access_token, encode_access_token
from app.auth.logged_out_tokens import LoggedOutTokenService
from app.auth.models import AuthAuditLog, User
from app.auth.password import hash_password, verify_password
from app.auth.refresh_tokens import (
    _ensure_aware,
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
    PermissionSlug,
    RegisterResponse,
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
from app.modules.admin import service as admin_service
from app.modules.admin.models import Permission, Role, RolePermission
from app.modules.staff_invites import repository as staff_invites_repository
from app.modules.staff_invites.models import StaffInvite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def serialize_user_identity(db: AsyncSession, user: User) -> UserRead:
    """Serialize one consistent product-door identity for auth responses."""
    permissions: list[PermissionSlug] = []
    role_name: str | None = None

    if user.role_id is not None:
        role_id_key = user.role_id.hex
        role_id_column = func.replace(cast(Role.id, String), "-", "")
        role_permission_role_id = func.replace(cast(RolePermission.role_id, String), "-", "")
        permission_id_column = func.replace(cast(Permission.id, String), "-", "")
        role_permission_permission_id = func.replace(
            cast(RolePermission.permission_id, String), "-", ""
        )
        result = await db.execute(
            select(Role.name, Permission.resource, Permission.action)
            .select_from(Role)
            .outerjoin(RolePermission, role_permission_role_id == role_id_column)
            .outerjoin(Permission, permission_id_column == role_permission_permission_id)
            .where(role_id_column == role_id_key)
            .distinct()
            .order_by(Permission.resource, Permission.action)
        )
        rows = result.all()
        role_name = rows[0].name if rows else None
        permissions = [
            PermissionSlug(resource=row.resource, action=row.action)
            for row in rows
            if row.resource is not None and row.action is not None
        ]

    identity = UserRead.model_validate(user)
    return identity.model_copy(
        update={
            "role_id": user.role_id,
            "role_name": role_name,
            "permissions": permissions,
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
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session),
) -> RegisterResponse:
    """
    Register new user account with email/password.

    Sends verification email after successful registration. Optionally accepts a
    staff invite token (machine-1-tenancy-core/05-org-invite-flow.md) -- an
    invalid/expired token never hard-fails registration, it just falls back to a
    normal candidate signup with a `warning` in the response.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Resolve an optional staff invite token. An invalid/expired token does NOT
    # hard-fail signup -- the user still gets a normal candidate account, and the
    # response carries a warning instead (see chunk 05's "Ambiguities resolved").
    invite: StaffInvite | None = None
    invite_warning: str | None = None
    if user_data.invite_token:
        invite = await staff_invites_repository.get_invite_by_token(db, user_data.invite_token)
        invite_expired = invite is not None and _ensure_aware(invite.expires_at) < datetime.now(UTC)
        if invite is None or invite.accepted_at is not None or invite_expired:
            invite = None
            invite_warning = (
                "Your invite link is invalid or has expired; "
                "your account was created without staff access."
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

    # Accept a valid staff invite: assign the requested role and mark it used.
    # Unlike the superseded org-invite design, this sets nothing else on `User`
    # -- there is no org/brand membership concept in this schema.
    if invite is not None:
        role_result = await db.execute(select(Role).where(Role.name == invite.role_name))
        role = role_result.scalar_one_or_none()
        if role is not None and invite.invited_by is not None:
            await admin_service.assign_role(
                db,
                actor_id=invite.invited_by,
                target_user_id=user.id,
                role_id=role.id,
                ip_address=get_client_ip(request),
            )
        else:
            # Defensive fallback only -- RBAC roles (team_owner/recruiter) are
            # fully merged, so this should not trigger in normal operation
            # (it can still happen if the inviter's account was later deleted,
            # since invited_by is SET NULL on delete).
            logger.warning(
                "Staff invite %s could not be resolved to a role assignment "
                "(role=%r, invited_by=%r); skipping role assignment.",
                invite.id,
                invite.role_name,
                invite.invited_by,
            )
        invite.accepted_at = datetime.now(UTC)
        await db.commit()

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

    return RegisterResponse(
        message="Registration successful. Please check your email to verify your account.",
        warning=invite_warning,
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
        user=await serialize_user_identity(db, user),
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
        user=await serialize_user_identity(db, user),
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
async def get_current_user(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> UserRead:
    """Get current user profile."""
    return await serialize_user_identity(db, current_user)


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
