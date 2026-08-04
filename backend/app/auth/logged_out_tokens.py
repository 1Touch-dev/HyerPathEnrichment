"""Dual Redis + PostgreSQL blacklist for logged-out tokens."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoggedOutToken

logger = logging.getLogger(__name__)


class LoggedOutTokenService:
    """Service for managing logged-out token blacklist (Redis + PostgreSQL)."""

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize service with Redis client.

        Args:
            redis_client: Async Redis client
        """
        self.redis = redis_client
        self.prefix = "logout:"

    async def add_logout_token(
        self, db: AsyncSession, user_id: UUID, token_jti: str, expires_at: datetime
    ) -> None:
        """
        Add token to blacklist (dual write to Redis + PostgreSQL).

        Args:
            db: Database session
            user_id: User UUID
            token_jti: JWT ID (jti claim)
            expires_at: Token expiration timestamp
        """
        # PostgreSQL: Durable storage + audit trail
        logout_token = LoggedOutToken(
            user_id=user_id,
            token_jti=token_jti,
            expires_at=expires_at,
        )
        db.add(logout_token)
        await db.commit()

        # Redis: Fast lookup with TTL
        ttl_seconds = int((expires_at - datetime.now(UTC)).total_seconds())
        if ttl_seconds > 0:
            await self.redis.setex(f"{self.prefix}{token_jti}", ttl_seconds, "revoked")

    async def is_token_logged_out(self, token_jti: str, db: AsyncSession | None = None) -> bool:
        """
        Check if token is in blacklist (fast Redis lookup, PostgreSQL fallback).

        Args:
            token_jti: JWT ID to check
            db: Optional database session for PostgreSQL fallback

        Returns:
            True if token is blacklisted, False otherwise
        """
        # 1. Check Redis first (fast, <1ms)
        cached = await self.redis.exists(f"{self.prefix}{token_jti}")
        if cached > 0:
            return True

        # 2. Fallback to PostgreSQL if Redis miss (slower, ~5-10ms)
        if db:
            result = await db.execute(
                select(LoggedOutToken)
                .where(LoggedOutToken.token_jti == token_jti)
                .where(LoggedOutToken.expires_at > datetime.now(UTC))
            )
            return result.scalar_one_or_none() is not None

        return False

    async def sync_blacklist_to_redis(self, db: AsyncSession) -> int:
        """
        Sync PostgreSQL blacklist to Redis (for restarts/failovers).

        Args:
            db: Database session

        Returns:
            Number of tokens synced
        """
        now = datetime.now(UTC)
        result = await db.execute(select(LoggedOutToken).where(LoggedOutToken.expires_at > now))
        tokens = result.scalars().all()

        synced = 0
        for token in tokens:
            ttl_seconds = int((token.expires_at - now).total_seconds())
            if ttl_seconds > 0:
                await self.redis.setex(f"{self.prefix}{token.token_jti}", ttl_seconds, "revoked")
                synced += 1

        logger.info(f"Synced {synced} logged-out tokens from PostgreSQL to Redis")
        return synced

    async def cleanup_expired_logout_tokens(self, db: AsyncSession) -> int:
        """
        Remove expired tokens from PostgreSQL (Redis auto-expires via TTL).

        Args:
            db: Database session

        Returns:
            Number of tokens deleted
        """
        now = datetime.now(UTC)
        result = await db.execute(delete(LoggedOutToken).where(LoggedOutToken.expires_at <= now))
        await db.commit()
        deleted = result.rowcount or 0  # type: ignore[attr-defined]
        logger.info(f"Cleaned up {deleted} expired logout tokens from PostgreSQL")
        return deleted

    async def verify_token_not_logged_out(
        self,
        db: AsyncSession,
        token_jti: str,
        user_id: UUID,
        ip_address: str,
        user_agent: str | None = None,
    ) -> None:
        """
        Verify token wasn't used after logout.

        If token is logged out, triggers security alert and raises exception.

        Args:
            db: Database session
            token_jti: JWT ID to verify
            user_id: User ID from token
            ip_address: Client IP address
            user_agent: Client User-Agent header

        Raises:
            HTTPException: 401 if token is logged out (likely stolen)
        """
        from fastapi import HTTPException, status

        from app.auth.models import AuthAuditLog

        if await self.is_token_logged_out(token_jti, db):
            # SECURITY: Token used after logout - likely stolen
            logger.warning(
                f"SECURITY ALERT: Token used after logout. "
                f"user_id={user_id}, jti={token_jti}, ip={ip_address}"
            )

            # Log security event
            audit_log = AuthAuditLog(
                user_id=user_id,
                event_type="suspicious_activity",
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="Token used after logout (possible token theft)",
                metadata={
                    "token_jti": token_jti,
                    "alert_type": "logged_out_token_reuse",
                },
            )
            db.add(audit_log)
            await db.commit()

            # TODO: Add additional security measures:
            # - Send email alert to user
            # - Trigger security team notification
            # - Consider revoking all user tokens

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please login again.",
            )
