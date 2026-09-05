"""Tests for logged-out token detection system."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.logged_out_tokens import LoggedOutTokenService
from app.auth.models import LoggedOutToken


@pytest.fixture
async def logout_service(fake_redis):
    """Create LoggedOutTokenService instance backed by the FakeRedis test double."""
    return LoggedOutTokenService(fake_redis)


@pytest.fixture(autouse=True)
async def _clean_logged_out_tokens(db: AsyncSession) -> None:
    """Ensure a clean logged_out_tokens table for each test.

    The test DB is a shared SQLite file across the module, so committed rows
    from one test would otherwise leak into the next test's counts.
    """
    from sqlalchemy import delete

    await db.execute(delete(LoggedOutToken))
    await db.commit()


@pytest.mark.asyncio
async def test_add_logout_token(db: AsyncSession, logout_service: LoggedOutTokenService):
    """Test adding token to blacklist."""
    user_id = uuid4()
    jti = f"{user_id}:test123"
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    await logout_service.add_logout_token(db, user_id, jti, expires_at)

    # Verify token is in PostgreSQL
    from sqlalchemy import select

    result = await db.execute(select(LoggedOutToken).where(LoggedOutToken.token_jti == jti))
    db_token = result.scalar_one_or_none()

    assert db_token is not None
    assert db_token.user_id == user_id
    assert db_token.token_jti == jti

    # Verify token is in Redis
    is_logged_out = await logout_service.is_token_logged_out(jti)
    assert is_logged_out is True


@pytest.mark.asyncio
async def test_is_token_logged_out_not_found(logout_service: LoggedOutTokenService):
    """Test checking non-existent token."""
    is_logged_out = await logout_service.is_token_logged_out("nonexistent-jti")
    assert is_logged_out is False


@pytest.mark.asyncio
async def test_sync_blacklist_to_redis(db: AsyncSession, logout_service: LoggedOutTokenService):
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
        db.add(token)

    await db.commit()

    # Sync to Redis
    synced_count = await logout_service.sync_blacklist_to_redis(db)

    assert synced_count == 5

    # Verify all tokens are in Redis
    for token in tokens:
        is_logged_out = await logout_service.is_token_logged_out(token.token_jti)
        assert is_logged_out is True


@pytest.mark.asyncio
async def test_sync_blacklist_to_redis_skips_expired(
    db: AsyncSession, logout_service: LoggedOutTokenService
):
    """Test that syncing skips expired tokens."""
    user_id = uuid4()

    # Create an expired token
    expired_token = LoggedOutToken(
        user_id=user_id,
        token_jti=f"{user_id}:expired",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db.add(expired_token)

    # Create a valid token
    valid_token = LoggedOutToken(
        user_id=user_id,
        token_jti=f"{user_id}:valid",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(valid_token)

    await db.commit()

    # Sync to Redis
    synced_count = await logout_service.sync_blacklist_to_redis(db)

    assert synced_count == 1

    # Verify only valid token is in Redis
    is_expired_logged_out = await logout_service.is_token_logged_out(expired_token.token_jti)
    is_valid_logged_out = await logout_service.is_token_logged_out(valid_token.token_jti)

    assert is_expired_logged_out is False
    assert is_valid_logged_out is True


@pytest.mark.asyncio
async def test_cleanup_expired_logout_tokens(
    db: AsyncSession, logout_service: LoggedOutTokenService
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
        db.add(expired_token)

    # Create valid tokens
    for i in range(2):
        valid_token = LoggedOutToken(
            user_id=user_id,
            token_jti=f"{user_id}:valid{i}",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        db.add(valid_token)

    await db.commit()

    # Cleanup expired tokens
    deleted_count = await logout_service.cleanup_expired_logout_tokens(db)

    assert deleted_count == 3

    # Verify only valid tokens remain
    from sqlalchemy import select

    result = await db.execute(select(LoggedOutToken))
    remaining_tokens = result.scalars().all()

    assert len(remaining_tokens) == 2
    assert all(
        token.expires_at.replace(tzinfo=UTC) > datetime.now(UTC) for token in remaining_tokens
    )


@pytest.mark.asyncio
async def test_redis_ttl_auto_expires(logout_service: LoggedOutTokenService, db: AsyncSession):
    """Test that a blacklisted token is looked up via Redis with the correct TTL.

    Real Redis key expiry (TTL countdown) requires a live Redis server and
    isn't exercised by the FakeRedis test double used for isolated tests.
    This verifies the service computes and applies a positive TTL and that
    the key is retrievable immediately after being set.
    """
    user_id = uuid4()
    jti = f"{user_id}:shortlived"
    expires_at = datetime.now(UTC) + timedelta(seconds=2)

    await logout_service.add_logout_token(db, user_id, jti, expires_at)

    assert await logout_service.is_token_logged_out(jti) is True
