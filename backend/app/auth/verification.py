"""Email verification service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import EmailVerificationToken, User
from app.auth.password import generate_secure_token
from app.core.config import get_settings
from app.services.email_service import EmailTemplate, enqueue_email


async def generate_verification_token(
    db: AsyncSession, user_id: UUID, expiry_hours: int = 24
) -> str:
    """
    Generate and store email verification token.

    Args:
        db: Database session
        user_id: User UUID
        expiry_hours: Token validity period (default 24h)

    Returns:
        Verification token string
    """
    # Delete any existing tokens for this user
    await db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
    )

    # Generate new token
    token = generate_secure_token(32)
    expires_at = datetime.now(UTC) + timedelta(hours=expiry_hours)

    # Store in database
    verification_token = EmailVerificationToken(token=token, user_id=user_id, expires_at=expires_at)
    db.add(verification_token)
    await db.commit()

    return token


async def send_verification_email(
    user_email: str, user_first_name: str, verification_token: str
) -> None:
    """
    Send verification email to user.

    Args:
        user_email: User's email address
        user_first_name: User's first name for personalization
        verification_token: Verification token
    """
    settings = get_settings()

    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

    # Enqueue email via background worker
    enqueue_email(
        template=EmailTemplate.EMAIL_VERIFICATION,
        recipient=user_email,
        context={
            "first_name": user_first_name,
            "verification_link": verification_link,
            "expiry_hours": 24,
        },
    )


async def verify_email_token(db: AsyncSession, token: str) -> User | None:
    """
    Verify email token and mark user as verified.

    Args:
        db: Database session
        token: Verification token from email

    Returns:
        User object if successful, None if token invalid/expired
    """
    # Find token
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        return None

    # Check expiry
    if token_record.expires_at < datetime.now(UTC):
        await db.delete(token_record)
        await db.commit()
        return None

    # Get user
    user_result = await db.execute(select(User).where(User.id == token_record.user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        return None

    # Mark user as verified
    user.is_verified = True
    user.verification_token = None
    user.verification_sent_at = None

    # Delete token
    await db.delete(token_record)
    await db.commit()
    await db.refresh(user)

    return user


async def resend_verification_email(db: AsyncSession, email: str) -> tuple[bool, str | None]:
    """
    Resend verification email to user with rate limiting.

    Args:
        db: Database session
        email: User's email address

    Returns:
        Tuple of (success, error_message)
        - (True, None) if email sent successfully
        - (False, error_msg) if failed with reason
    """
    # Find user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        return False, "User not found"

    if user.is_verified:
        return False, "Email already verified"

    # Rate limit: Check if last email was sent within 5 minutes
    if user.verification_sent_at:
        time_since_last = datetime.now(UTC) - user.verification_sent_at
        cooldown_seconds = 5 * 60  # 5 minutes
        if time_since_last.total_seconds() < cooldown_seconds:
            remaining_seconds = int(cooldown_seconds - time_since_last.total_seconds())
            remaining_minutes = remaining_seconds // 60
            remaining_secs = remaining_seconds % 60
            error_msg = f"Please wait {remaining_minutes}m {remaining_secs}s before requesting another verification email"
            return False, error_msg

    # Generate new token
    token = await generate_verification_token(db, user.id)

    # Send email
    await send_verification_email(user.email, user.first_name, token)

    # Update sent timestamp
    user.verification_sent_at = datetime.now(UTC)
    await db.commit()

    return True, None


async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """
    Remove expired email verification tokens.

    This should be run as a scheduled task (e.g., daily cron job).

    Args:
        db: Database session

    Returns:
        Number of tokens deleted
    """
    result = await db.execute(
        delete(EmailVerificationToken)
        .where(EmailVerificationToken.expires_at < datetime.now(UTC))
        .returning(EmailVerificationToken.token)
    )
    deleted_count = len(result.all())
    await db.commit()

    return deleted_count
