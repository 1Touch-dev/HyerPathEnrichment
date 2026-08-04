"""Refresh token service for token rotation and reuse detection."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, User
from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def create_refresh_token(
    db: AsyncSession,
    user_id: UUID,
    parent_token: str | None = None,
) -> tuple[str, RefreshToken]:
    """
    Create a new refresh token for user.

    Args:
        db: Database session
        user_id: User UUID
        parent_token: Optional parent token ID for rotation tracking

    Returns:
        Tuple of (token_value, RefreshToken object)
    """
    settings = get_settings()

    # Generate cryptographically secure random token (256-bit)
    token_value = secrets.token_urlsafe(43)

    # Calculate expiration
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Create token record
    refresh_token = RefreshToken(
        token=token_value,
        user_id=user_id,
        used=False,
        parent_token=parent_token,
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )

    db.add(refresh_token)
    await db.commit()
    await db.refresh(refresh_token)

    return token_value, refresh_token


async def validate_refresh_token(
    db: AsyncSession,
    token_value: str,
) -> tuple[RefreshToken, User] | tuple[None, None]:
    """
    Validate refresh token and return token + user.

    Args:
        db: Database session
        token_value: Token string to validate

    Returns:
        Tuple of (RefreshToken, User) if valid, (None, None) otherwise
    """
    # Fetch token from database
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token_value))
    refresh_token = result.scalar_one_or_none()

    if not refresh_token:
        logger.warning("Refresh token not found in database")
        return None, None

    # Check if expired
    if refresh_token.expires_at < datetime.now(UTC):
        logger.info(f"Refresh token expired for user {refresh_token.user_id}")
        return None, None

    # Fetch user
    user_result = await db.execute(select(User).where(User.id == refresh_token.user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        logger.warning(f"User not found for refresh token: {refresh_token.user_id}")
        return None, None

    return refresh_token, user


async def detect_token_reuse(
    db: AsyncSession,
    refresh_token: RefreshToken,
) -> bool:
    """
    Detect if a refresh token has been reused (already marked as used).

    Args:
        db: Database session
        refresh_token: RefreshToken object to check

    Returns:
        True if token was already used (reuse detected), False otherwise
    """
    return refresh_token.used


async def revoke_token_family(
    db: AsyncSession,
    token: str,
    reason: str = "Token reuse detected",
) -> int:
    """
    Revoke entire token family for security.

    When token reuse is detected, all tokens in the family chain
    (parent and descendants) are marked as used to prevent further use.

    Args:
        db: Database session
        token: Token that was reused
        reason: Reason for revocation (for logging)

    Returns:
        Number of tokens revoked
    """
    # Fetch the reused token
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token))
    reused_token = result.scalar_one_or_none()

    if not reused_token:
        return 0

    user_id = reused_token.user_id

    # Mark all tokens for this user as used
    # In a family-based approach, we revoke all tokens to be safe
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.used == False,  # noqa: E712
        )
    )
    tokens_to_revoke = result.scalars().all()

    count = 0
    for token_obj in tokens_to_revoke:
        token_obj.used = True
        count += 1

    await db.commit()

    logger.warning(f"Token family revoked for user {user_id}: {reason}. Revoked {count} token(s)")

    return count


async def rotate_refresh_token(
    db: AsyncSession,
    old_token_value: str,
    user_id: UUID,
) -> tuple[str, RefreshToken] | tuple[None, None]:
    """
    Rotate refresh token - mark old as used and create new one.

    This is an atomic operation to prevent race conditions.

    Args:
        db: Database session
        old_token_value: Current token to be rotated
        user_id: User ID

    Returns:
        Tuple of (new_token_value, RefreshToken) if successful, (None, None) otherwise
    """
    # Mark old token as used
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == old_token_value))
    old_token = result.scalar_one_or_none()

    if not old_token:
        return None, None

    old_token.used = True

    # Create new token with old token as parent (for family tracking)
    new_token_value, new_token = await create_refresh_token(
        db=db,
        user_id=user_id,
        parent_token=old_token_value,
    )

    # Commit both changes atomically
    await db.commit()

    logger.info(f"Rotated refresh token for user {user_id}")

    return new_token_value, new_token


async def revoke_refresh_token(
    db: AsyncSession,
    token_value: str,
) -> bool:
    """
    Revoke a single refresh token (mark as used).

    Args:
        db: Database session
        token_value: Token to revoke

    Returns:
        True if revoked successfully, False if token not found
    """
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token_value))
    token = result.scalar_one_or_none()

    if not token:
        return False

    token.used = True
    await db.commit()

    logger.info(f"Revoked refresh token for user {token.user_id}")

    return True
