"""Tests for email verification functionality."""

import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import EmailVerificationToken, User
from app.auth.password import hash_password
from app.auth.verification import (
    generate_verification_token,
    verify_email_token,
    resend_verification_email,
)


@pytest.mark.asyncio
async def test_generate_verification_token(db_session: AsyncSession):
    """Test verification token generation."""
    # Create a test user
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Generate token
    token = await generate_verification_token(db_session, user.id)

    assert token is not None
    assert len(token) > 40  # Should be a secure URL-safe token

    # Verify token was saved to database
    from sqlalchemy import select

    result = await db_session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    db_token = result.scalar_one_or_none()

    assert db_token is not None
    assert db_token.token == token
    assert db_token.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_generate_verification_token_replaces_old(db_session: AsyncSession):
    """Test that generating a new token deletes the old one."""
    # Create a test user
    user = User(
        email="test2@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Generate first token
    token1 = await generate_verification_token(db_session, user.id)

    # Generate second token
    token2 = await generate_verification_token(db_session, user.id)

    assert token1 != token2

    # Verify only one token exists
    from sqlalchemy import select

    result = await db_session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    tokens = result.scalars().all()

    assert len(tokens) == 1
    assert tokens[0].token == token2


@pytest.mark.asyncio
async def test_verify_email_token_success(db_session: AsyncSession):
    """Test successful email verification."""
    # Create a test user
    user = User(
        email="test3@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Generate token
    token = await generate_verification_token(db_session, user.id)

    # Verify token
    verified_user = await verify_email_token(db_session, token)

    assert verified_user is not None
    assert verified_user.id == user.id
    assert verified_user.is_verified is True
    assert verified_user.verification_token is None
    assert verified_user.verification_sent_at is None

    # Verify token was deleted
    from sqlalchemy import select

    result = await db_session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    db_token = result.scalar_one_or_none()

    assert db_token is None


@pytest.mark.asyncio
async def test_verify_email_token_invalid(db_session: AsyncSession):
    """Test verification with invalid token."""
    result = await verify_email_token(db_session, "invalid-token-12345")
    assert result is None


@pytest.mark.asyncio
async def test_verify_email_token_expired(db_session: AsyncSession):
    """Test verification with expired token."""
    # Create a test user
    user = User(
        email="test4@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create an expired token
    from app.auth.password import generate_secure_token

    token = generate_secure_token(32)
    expired_token = EmailVerificationToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(UTC) - timedelta(hours=1),  # Expired 1 hour ago
    )
    db_session.add(expired_token)
    await db_session.commit()

    # Try to verify with expired token
    result = await verify_email_token(db_session, token)

    assert result is None

    # Verify token was deleted
    from sqlalchemy import select

    result = await db_session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    db_token = result.scalar_one_or_none()

    assert db_token is None


@pytest.mark.asyncio
async def test_resend_verification_email_success(db_session: AsyncSession):
    """Test resending verification email."""
    # Create an unverified user
    user = User(
        email="test5@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Resend verification (with mocked email)
    success = await resend_verification_email(db_session, user.email)

    assert success is True

    # Verify new token was created
    from sqlalchemy import select

    result = await db_session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    token = result.scalar_one_or_none()

    assert token is not None
    assert token.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_resend_verification_email_already_verified(db_session: AsyncSession):
    """Test resending verification to already verified user."""
    # Create a verified user
    user = User(
        email="test6@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("Test123!"),
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    # Try to resend verification
    success = await resend_verification_email(db_session, user.email)

    assert success is False


@pytest.mark.asyncio
async def test_resend_verification_email_not_found(db_session: AsyncSession):
    """Test resending verification to non-existent user."""
    success = await resend_verification_email(db_session, "nonexistent@example.com")

    assert success is False
