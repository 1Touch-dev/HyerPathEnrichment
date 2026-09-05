"""Refresh token service for token rotation and reuse detection."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, User
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def hash_refresh_token(raw: str) -> str:
    """SHA-256 hex digest of a refresh token (high-entropy; no salt needed)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_aware(dt: datetime) -> datetime:
    """
    Normalize a datetime to be timezone-aware (UTC).

    SQLite does not persist tzinfo even for DateTime(timezone=True) columns,
    so values read back from the DB come back naive. Treat naive values as UTC
    to allow safe comparison against datetime.now(UTC).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def _get_refresh_token_row(db: AsyncSession, raw_token: str) -> RefreshToken | None:
    """Lookup by hashed PK, with dual-read fallback for pre-hash plaintext rows."""
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token_hash))
    row = result.scalar_one_or_none()
    if row is not None:
        return row

    # Legacy plaintext rows (pre-P1): upgrade in place on successful hit.
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == raw_token))
    row = result.scalar_one_or_none()
    if row is None:
        return None

    parent = row.parent_token
    if parent and len(parent) != 64:
        # Likely plaintext parent; hash it for consistency.
        parent = hash_refresh_token(parent)

    # Primary key update: delete+reinsert is safer across dialects than UPDATE PK.
    upgraded = RefreshToken(
        token=token_hash,
        user_id=row.user_id,
        used=row.used,
        parent_token=parent,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )
    await db.delete(row)
    db.add(upgraded)
    await db.flush()
    return upgraded


async def create_refresh_token(
    db: AsyncSession,
    user_id: UUID,
    parent_token: str | None = None,
) -> tuple[str, RefreshToken]:
    """
    Create a new refresh token for user.

    Returns the raw token for the cookie; stores only the SHA-256 hash in the DB.
    ``parent_token`` may be raw or already-hashed; it is normalized to a hash.
    """
    settings = get_settings()

    token_value = secrets.token_urlsafe(43)
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    parent_hash: str | None = None
    if parent_token:
        parent_hash = (
            parent_token
            if len(parent_token) == 64 and all(c in "0123456789abcdef" for c in parent_token)
            else hash_refresh_token(parent_token)
        )

    refresh_token = RefreshToken(
        token=hash_refresh_token(token_value),
        user_id=user_id,
        used=False,
        parent_token=parent_hash,
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
    """Validate refresh token and return token + user."""
    refresh_token = await _get_refresh_token_row(db, token_value)

    if not refresh_token:
        logger.warning("Refresh token not found in database")
        return None, None

    if _ensure_aware(refresh_token.expires_at) < datetime.now(UTC):
        logger.info(f"Refresh token expired for user {refresh_token.user_id}")
        return None, None

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
    """Detect if a refresh token has been reused (already marked as used)."""
    return refresh_token.used


async def revoke_token_family(
    db: AsyncSession,
    token: str,
    reason: str = "Token reuse detected",
) -> int:
    """Revoke all unused refresh tokens for the user that owns ``token``."""
    reused_token = await _get_refresh_token_row(db, token)

    if not reused_token:
        # Also try treating input as an already-hashed PK (reuse path may pass hash).
        result = await db.execute(select(RefreshToken).where(RefreshToken.token == token))
        reused_token = result.scalar_one_or_none()

    if not reused_token:
        return 0

    return await revoke_all_refresh_tokens(db, reused_token.user_id, reason=reason)


async def revoke_all_refresh_tokens(
    db: AsyncSession,
    user_id: UUID,
    *,
    reason: str = "revoke all sessions",
) -> int:
    """Mark all unused refresh tokens for a user as used."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            ~RefreshToken.used,
        )
    )
    tokens_to_revoke = result.scalars().all()

    count = 0
    for token_obj in tokens_to_revoke:
        token_obj.used = True
        count += 1

    await db.commit()
    logger.warning(
        "Refresh tokens revoked for user %s: %s. Revoked %s token(s)",
        user_id,
        reason,
        count,
    )
    return count


async def rotate_refresh_token(
    db: AsyncSession,
    old_token_value: str,
    user_id: UUID,
) -> tuple[str, RefreshToken] | tuple[None, None]:
    """Rotate refresh token — mark old as used and create new one."""
    old_token = await _get_refresh_token_row(db, old_token_value)

    if not old_token:
        return None, None

    old_token.used = True
    old_token_hash = old_token.token

    new_token_value, new_token = await create_refresh_token(
        db=db,
        user_id=user_id,
        parent_token=old_token_hash,
    )

    await db.commit()

    logger.info(f"Rotated refresh token for user {user_id}")

    return new_token_value, new_token


async def revoke_refresh_token(
    db: AsyncSession,
    token_value: str,
) -> bool:
    """Revoke a single refresh token (mark as used)."""
    token = await _get_refresh_token_row(db, token_value)

    if not token:
        return False

    token.used = True
    await db.commit()

    logger.info(f"Revoked refresh token for user {token.user_id}")

    return True
