"""Tests for logged-out token detection system."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.logged_out_tokens import LoggedOutTokenService
from app.auth.models import LoggedOutToken


@pytest.fixture
async def redis_client():
    """Create a test Redis client (use fakeredis for testing)."""
    # In real tests, you'd use fakeredis
    # For this example, we'll use a real Redis instance
    client = redis.from_url("redis://localhost:6379/15")  # Use DB 15 for tests
    yield client
    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
async def logout_service(redis_client):
    """Create LoggedOutTokenService instance."""
    return LoggedOutTokenService(redis_client)


@pytest.mark.asyncio
async def test_add_logout_token(db_session: AsyncSession, logout_service: LoggedOutTokenService):
    """Test adding token to blacklist."""
    user_id = uuid4()
    jti = f"{user_id}:test123"
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    await logout_service.add_logout_token(db_session, user_id, jti, expires_at)

    # Verify token is in PostgreSQL
    from sqlalchemy import select

    result = await db_session.execute(select(LoggedOutToken).where(LoggedOutToken.token_jti == jti))
    db_token = result.scalar_one_or_none()

    assert db_token is not None
    assert db_token.user_id == user_id
    assert db_token.token_jti == jti
    assert db_token.expires_at == expires_at

    # Verify token is in Redis
    is_logged_out = await logout_service.is_token_logged_out(jti)
    assert is_logged_out is True


@pytest.mark.asyncio
async def test_is_token_logged_out_not_found(logout_service: LoggedOutTokenService):
    """Test checking non-existent token."""
    is_logged_out = await logout_service.is_token_logged_out("nonexistent-jti")
    assert is_logged_out is False


@pytest.mark.asyncio
async def test_sync_blacklist_to_redis(
    db_session: AsyncSession, logout_service: LoggedOutTokenService
):
    """Test syncing PostgreSQL blacklist to Redis."""
    # Create some logged-out tokens in PostgreSQL
    user_id = uuid4()
    tokens = []
    for i in range(5):
        jti = f"{user_id}:test{i}"
        token = LoggedOutToken(
            user_id=user_id,
            token_jti=jti,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        tokens.append(token)
        db_session.add(token)

    await db_session.commit()

    # Sync to Redis
    synced_count = await logout_service.sync_blacklist_to_redis(db_session)

    assert synced_count == 5

    # Verify all tokens are in Redis
    for token in tokens:
        is_logged_out = await logout_service.is_token_logged_out(token.token_jti)
        assert is_logged_out is True


@pytest.mark.asyncio
async def test_sync_blacklist_to_redis_skips_expired(
    db_session: AsyncSession, logout_service: LoggedOutTokenService
):
    """Test that syncing skips expired tokens."""
    user_id = uuid4()

    # Create an expired token
    expired_token = LoggedOutToken(
        user_id=user_id,
        token_jti=f"{user_id}:expired",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(expired_token)

    # Create a valid token
    valid_token = LoggedOutToken(
        user_id=user_id,
        token_jti=f"{user_id}:valid",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db_session.add(valid_token)

    await db_session.commit()

    # Sync to Redis
    synced_count = await logout_service.sync_blacklist_to_redis(db_session)

    assert synced_count == 1

    # Verify only valid token is in Redis
    is_expired_logged_out = await logout_service.is_token_logged_out(expired_token.token_jti)
    is_valid_logged_out = await logout_service.is_token_logged_out(valid_token.token_jti)

    assert is_expired_logged_out is False
    assert is_valid_logged_out is True


@pytest.mark.asyncio
async def test_cleanup_expired_logout_tokens(
    db_session: AsyncSession, logout_service: LoggedOutTokenService
):
    """Test cleanup of expired tokens from PostgreSQL."""
    user_id = uuid4()

    # Create expired tokens
    for i in range(3):
        expired_token = LoggedOutToken(
            user_id=user_id,
            token_jti=f"{user_id}:expired{i}",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(expired_token)

    # Create valid tokens
    for i in range(2):
        valid_token = LoggedOutToken(
            user_id=user_id,
            token_jti=f"{user_id}:valid{i}",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        db_session.add(valid_token)

    await db_session.commit()

    # Cleanup expired tokens
    deleted_count = await logout_service.cleanup_expired_logout_tokens(db_session)

    assert deleted_count == 3

    # Verify only valid tokens remain
    from sqlalchemy import select

    result = await db_session.execute(select(LoggedOutToken))
    remaining_tokens = result.scalars().all()

    assert len(remaining_tokens) == 2
    assert all(token.expires_at > datetime.now(UTC) for token in remaining_tokens)


@pytest.mark.asyncio
async def test_redis_ttl_auto_expires(
    logout_service: LoggedOutTokenService, db_session: AsyncSession
):
    """Test that Redis keys auto-expire based on TTL."""
    user_id = uuid4()
    jti = f"{user_id}:shortlived"
    # Set expiry to 2 seconds in the future
    expires_at = datetime.now(UTC) + timedelta(seconds=2)

    await logout_service.add_logout_token(db_session, user_id, jti, expires_at)

    # Verify token is initially blacklisted
    assert await logout_service.is_token_logged_out(jti) is True

    # Wait for token to expire
    import asyncio

    await asyncio.sleep(3)

    # Verify token is no longer in Redis (auto-expired by TTL)
    assert await logout_service.is_token_logged_out(jti) is False
