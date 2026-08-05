"""Integration test configuration for REAL infrastructure testing.

This configuration uses:
- PostgreSQL with pgvector (not SQLite)
- Real Redis (not FakeRedis)
- Real RQ workers
- Real OpenAI API (costs money!)
- Real R2 storage

DO NOT run this in CI - only for local/staging testing with real services.
"""

from __future__ import annotations

import os
from uuid import UUID

import pytest
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.database.session import get_db_session

# Use REAL PostgreSQL from Docker Compose
os.environ["DATABASE_URL"] = get_settings().database_url
os.environ["REDIS_URL"] = get_settings().redis_url
os.environ["API_TOKEN"] = "change-me"

# Ensure we're using production config
print(f"[TEST CONFIG] Database: {get_settings().database_url}")
print(f"[TEST CONFIG] Redis: {get_settings().redis_url}")
print(f"[TEST CONFIG] R2 Enabled: {get_settings().r2_enabled}")
print(f"[TEST CONFIG] Embeddings Enabled: {get_settings().enable_embeddings}")
print(f"[TEST CONFIG] OpenAI Model: {get_settings().openai_embedding_model}")


@pytest.fixture(scope="session", autouse=True)
def verify_real_infrastructure():
    """Verify all real services are available before running tests."""
    print("\n=== Verifying Real Infrastructure ===")

    # 1. Check PostgreSQL with pgvector
    db_url = get_settings().database_url
    if "postgresql" not in db_url:
        pytest.exit("ERROR: Not using PostgreSQL! Set DATABASE_URL in .env.production")

    # 2. Check Redis URL
    redis_url = get_settings().redis_url
    if "redis:" not in redis_url:
        pytest.exit("ERROR: Not using real Redis! Set REDIS_URL in .env.production")

    # 3. Check OpenAI API key
    if not get_settings().openai_api_key:
        pytest.exit("ERROR: OpenAI API key not set! Set OPENAI_API_KEY in .env.production")

    # 4. Warn about costs
    print("\n⚠️  WARNING: These tests will incur real costs:")
    print("   - OpenAI API calls (~$0.01 per test run)")
    print("   - R2 storage usage")
    print("   - PostgreSQL resources")
    print("\n✓ All infrastructure checks passed")
    print("=" * 50 + "\n")


@pytest.fixture
async def db():
    """Provide async database session for tests (REAL PostgreSQL)."""
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        yield session
        await session.rollback()


async def test_auth_dependency(
    authorization: str | None = Header(None),
    x_test_user_id: str | None = Header(None, alias="X-Test-User-ID"),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Test authentication dependency that supports X-Test-User-ID header.

    This allows tests to bypass cookie-based JWT auth and directly specify a test user.
    """
    # In test mode, allow X-Test-User-ID header to specify user
    if x_test_user_id:
        user_uuid = UUID(x_test_user_id)

        # Check if user exists
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

        if not user:
            # Create test user on the fly
            user = User(
                id=user_uuid,
                email=f"test_{str(user_uuid)[:8]}@example.com",
                first_name="Test",
                last_name="User",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        return user

    # Otherwise require valid API token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token"
        )

    token = authorization.replace("Bearer ", "")
    if token != get_settings().api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Return a default test user for valid token
    result = await db.execute(select(User).where(User.email == "test@example.com").limit(1))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


@pytest.fixture(autouse=True)
async def override_auth_for_tests() -> None:
    """Override authentication dependencies to use test auth."""
    from app.auth.dependencies import get_current_user_from_cookie, require_verified_user
    from app.main import app

    # Override dependencies for test mode
    app.dependency_overrides[get_current_user_from_cookie] = test_auth_dependency
    app.dependency_overrides[require_verified_user] = test_auth_dependency

    yield

    # Clean up overrides after test
    app.dependency_overrides.clear()


# NO FakeRedis - use real Redis!
# NO SQLite - use real PostgreSQL!
# This is REAL infrastructure testing!
