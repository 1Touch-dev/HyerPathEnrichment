"""Tests for email verification functionality."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import EmailVerificationToken, User
from app.auth.password import hash_password
from app.auth.verification import (
    generate_verification_token,
    resend_verification_email,
    verify_email_token,
)


@pytest.mark.asyncio
async def test_generate_verification_token(db: AsyncSession):
    """Test verification token generation."""
    # Create a test user
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate token
    token = await generate_verification_token(db, user.id)

    assert token is not None
    assert len(token) > 40  # Should be a secure URL-safe token

    # Verify token was saved to database
    from sqlalchemy import select

    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    db_token = result.scalar_one_or_none()

    assert db_token is not None
    assert db_token.token == token
    assert db_token.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_generate_verification_token_replaces_old(db: AsyncSession):
    """Test that generating a new token deletes the old one."""
    # Create a test user
    user = User(
        email="test2@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate first token
    token1 = await generate_verification_token(db, user.id)

    # Generate second token
    token2 = await generate_verification_token(db, user.id)

    assert token1 != token2

    # Verify only one token exists
    from sqlalchemy import select

    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    tokens = result.scalars().all()

    assert len(tokens) == 1
    assert tokens[0].token == token2


@pytest.mark.asyncio
async def test_verify_email_token_success(db: AsyncSession):
    """Test successful email verification."""
    # Create a test user
    user = User(
        email="test3@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate token
    token = await generate_verification_token(db, user.id)

    # Verify token
    verified_user = await verify_email_token(db, token)

    assert verified_user is not None
    assert verified_user.id == user.id
    assert verified_user.is_verified is True
    assert verified_user.verification_token is None
    assert verified_user.verification_sent_at is None

    # Verify token was deleted
    from sqlalchemy import select

    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    db_token = result.scalar_one_or_none()

    assert db_token is None


@pytest.mark.asyncio
async def test_verify_email_token_invalid(db: AsyncSession):
    """Test verification with invalid token."""
    result = await verify_email_token(db, "invalid-token-12345")
    assert result is None


@pytest.mark.asyncio
async def test_verify_email_token_expired(db: AsyncSession):
    """Test verification with expired token."""
    # Create a test user
    user = User(
        email="test4@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create an expired token
    from app.auth.password import generate_secure_token

    token = generate_secure_token(32)
    expired_token = EmailVerificationToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(UTC) - timedelta(hours=1),  # Expired 1 hour ago
    )
    db.add(expired_token)
    await db.commit()

    # Try to verify with expired token
    result = await verify_email_token(db, token)

    assert result is None

    # Verify token was deleted
    from sqlalchemy import select

    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    db_token = result.scalar_one_or_none()

    assert db_token is None


@pytest.mark.asyncio
async def test_resend_verification_email_success(db: AsyncSession):
    """Test resending verification email."""
    # Create an unverified user
    user = User(
        email="test5@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Resend verification (with mocked email)
    success, error = await resend_verification_email(db, user.email)

    assert success is True
    assert error is None

    # Verify new token was created
    from sqlalchemy import select

    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    token = result.scalar_one_or_none()

    assert token is not None
    assert token.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_resend_verification_email_already_verified(db: AsyncSession):
    """Test resending verification to already verified user."""
    # Create a verified user
    user = User(
        email="test6@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()

    # Try to resend verification
    success, error = await resend_verification_email(db, user.email)

    assert success is False
    assert error == "Email already verified"


@pytest.mark.asyncio
async def test_resend_verification_email_not_found(db: AsyncSession):
    """Test resending verification to non-existent user."""
    success, error = await resend_verification_email(db, "nonexistent@example.com")

    assert success is False
    assert error == "User not found"
