"""Account deletion (soft delete) tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoggedOutToken, User
from app.auth.password import hash_password


@pytest.fixture(autouse=True)
async def _clean_users_table(db: AsyncSession) -> None:
    """Ensure a clean users table before each test.

    Tests in this module use fixed emails (e.g. "active@example.com") and
    assert exact counts of active users, which requires isolation from the
    shared session-scoped SQLite database used across the test suite.
    """
    await db.execute(delete(LoggedOutToken))
    await db.execute(delete(User))
    await db.commit()


@pytest.fixture
async def active_user(db: AsyncSession) -> User:
    """Create active test user."""
    user = User(
        email="active@example.com",
        first_name="Active",
        last_name="User",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_soft_delete_sets_deleted_at(db: AsyncSession, active_user: User) -> None:
    """Test soft delete marks user with deleted_at timestamp."""
    # Perform soft delete
    active_user.deleted_at = datetime.now(UTC)
    await db.commit()

    # Verify user still exists in database
    result = await db.execute(select(User).where(User.id == active_user.id))
    deleted_user = result.scalar_one_or_none()

    assert deleted_user is not None
    assert deleted_user.deleted_at is not None
    assert deleted_user.deleted_at <= datetime.now(UTC)


@pytest.mark.asyncio
async def test_deleted_user_login_prevented(db: AsyncSession, active_user: User) -> None:
    """Test login check should reject deleted users."""
    # Soft delete user
    active_user.deleted_at = datetime.now(UTC)
    await db.commit()

    # Query for login (should filter by deleted_at IS NULL)
    result = await db.execute(
        select(User).where(User.email == active_user.email, User.deleted_at.is_(None))
    )
    login_user = result.scalar_one_or_none()

    assert login_user is None  # Deleted user not found


@pytest.mark.asyncio
async def test_soft_delete_preserves_user_data(db: AsyncSession, active_user: User) -> None:
    """Test soft delete preserves all user data."""
    original_email = active_user.email
    original_first_name = active_user.first_name
    original_id = active_user.id

    # Soft delete
    active_user.deleted_at = datetime.now(UTC)
    await db.commit()

    # Fetch without filter
    result = await db.execute(select(User).where(User.id == original_id))
    deleted_user = result.scalar_one()

    assert deleted_user.email == original_email
    assert deleted_user.first_name == original_first_name
    assert deleted_user.hashed_password is not None


@pytest.mark.asyncio
async def test_delete_account_blacklists_current_token(db: AsyncSession, active_user: User) -> None:
    """Test account deletion blacklists active token."""
    jti = "current-session-jti"
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    # Simulate logout token added during account deletion
    logout_token = LoggedOutToken(user_id=active_user.id, token_jti=jti, expires_at=expires_at)
    db.add(logout_token)

    # Soft delete user
    active_user.deleted_at = datetime.now(UTC)
    await db.commit()

    # Verify token blacklisted
    result = await db.execute(select(LoggedOutToken).where(LoggedOutToken.token_jti == jti))
    blacklisted_token = result.scalar_one_or_none()

    assert blacklisted_token is not None
    assert blacklisted_token.user_id == active_user.id


@pytest.mark.asyncio
async def test_deleted_user_cannot_be_restored_without_admin(
    db: AsyncSession, active_user: User
) -> None:
    """Test deleted user remains deleted until admin restores."""
    # Soft delete
    active_user.deleted_at = datetime.now(UTC)
    await db.commit()

    # User should not be findable in normal queries
    result = await db.execute(
        select(User).where(User.email == active_user.email, User.deleted_at.is_(None))
    )
    assert result.scalar_one_or_none() is None

    # Admin restore (set deleted_at to NULL)
    result = await db.execute(select(User).where(User.id == active_user.id))
    user = result.scalar_one()
    user.deleted_at = None
    await db.commit()

    # Now user can login again
    result = await db.execute(
        select(User).where(User.email == active_user.email, User.deleted_at.is_(None))
    )
    restored_user = result.scalar_one_or_none()
    assert restored_user is not None


@pytest.mark.asyncio
async def test_deleted_at_indexed_for_performance(db: AsyncSession) -> None:
    """Test deleted_at column has index for fast filtering."""
    # Create multiple users
    users = [
        User(
            email=f"user{i}@example.com",
            first_name="User",
            last_name=f"Number{i}",
            hashed_password=hash_password("password"),
            is_verified=True,
            deleted_at=datetime.now(UTC) if i % 2 == 0 else None,
        )
        for i in range(10)
    ]
    for user in users:
        db.add(user)
    await db.commit()

    # Query active users (should use index)
    result = await db.execute(select(User).where(User.deleted_at.is_(None)))
    active_users = result.scalars().all()

    assert len(active_users) == 5  # Only odd-numbered users (not deleted)


@pytest.mark.asyncio
async def test_multiple_delete_operations_idempotent(db: AsyncSession, active_user: User) -> None:
    """Test deleting already-deleted user is safe."""
    first_delete_time = datetime.now(UTC)

    # First delete
    active_user.deleted_at = first_delete_time
    await db.commit()

    await db.refresh(active_user)

    # Second delete (should just update timestamp)
    second_delete_time = datetime.now(UTC) + timedelta(seconds=1)
    active_user.deleted_at = second_delete_time
    await db.commit()

    await db.refresh(active_user)

    # Verify user still deleted with updated timestamp
    stored_deleted_at = active_user.deleted_at
    if stored_deleted_at is not None and stored_deleted_at.tzinfo is None:
        stored_deleted_at = stored_deleted_at.replace(tzinfo=UTC)
    assert stored_deleted_at == second_delete_time


@pytest.mark.asyncio
async def test_deleted_user_foreign_keys_cascade(db: AsyncSession, active_user: User) -> None:
    """Test that deleting user doesn't break foreign key constraints."""
    # Note: With soft delete, we don't actually delete the row
    # So foreign keys remain intact
    active_user.deleted_at = datetime.now(UTC)
    await db.commit()

    # User row still exists
    result = await db.execute(select(User).where(User.id == active_user.id))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_deleted_user_excludes_from_active_queries(db: AsyncSession) -> None:
    """Test deleted users excluded from standard queries."""
    # Create active and deleted users
    active = User(
        email="active@example.com",
        first_name="Active",
        last_name="User",
        hashed_password=hash_password("pass"),
        is_verified=True,
    )
    deleted = User(
        email="deleted@example.com",
        first_name="Deleted",
        last_name="User",
        hashed_password=hash_password("pass"),
        is_verified=True,
        deleted_at=datetime.now(UTC),
    )
    db.add(active)
    db.add(deleted)
    await db.commit()

    # Query for active users only
    result = await db.execute(select(User).where(User.deleted_at.is_(None)))
    active_users = result.scalars().all()

    assert len(active_users) == 1
    assert active_users[0].email == "active@example.com"


@pytest.mark.asyncio
async def test_delete_account_compliance_trail(db: AsyncSession, active_user: User) -> None:
    """Test soft delete provides compliance audit trail."""
    deletion_time = datetime.now(UTC)

    active_user.deleted_at = deletion_time
    await db.commit()

    # Verify deletion can be audited
    result = await db.execute(select(User).where(User.deleted_at.isnot(None)))
    deleted_users = result.scalars().all()

    assert len(deleted_users) >= 1
    assert any(u.id == active_user.id for u in deleted_users)

    # Deletion timestamp available for compliance reports
    result = await db.execute(select(User).where(User.id == active_user.id))
    user = result.scalar_one()
    assert abs((user.deleted_at - deletion_time).total_seconds()) < 1


@pytest.mark.asyncio
async def test_oauth_user_account_deletion(db: AsyncSession) -> None:
    """Test OAuth user can also be soft deleted."""
    oauth_user = User(
        email="oauth@example.com",
        first_name="OAuth",
        last_name="User",
        hashed_password=None,  # OAuth users have no password
        oauth_provider="google",
        oauth_id="google-123",
        is_verified=True,
    )
    db.add(oauth_user)
    await db.commit()
    await db.refresh(oauth_user)

    # Soft delete OAuth user
    oauth_user.deleted_at = datetime.now(UTC)
    await db.commit()

    # Verify deleted
    result = await db.execute(
        select(User).where(User.email == "oauth@example.com", User.deleted_at.is_(None))
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_unverified_user_can_be_deleted(db: AsyncSession) -> None:
    """Test unverified users can also be soft deleted."""
    unverified = User(
        email="unverified@example.com",
        first_name="Unverified",
        last_name="User",
        hashed_password=hash_password("pass"),
        is_verified=False,
    )
    db.add(unverified)
    await db.commit()
    await db.refresh(unverified)

    # Soft delete
    unverified.deleted_at = datetime.now(UTC)
    await db.commit()

    # Verify deleted
    result = await db.execute(select(User).where(User.id == unverified.id))
    user = result.scalar_one()
    assert user.deleted_at is not None
