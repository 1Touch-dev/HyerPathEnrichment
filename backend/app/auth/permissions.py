"""Permission helpers for access control."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user_from_cookie
from app.auth.models import User


async def require_verified_user(
    user: User = Depends(get_current_user_from_cookie),
) -> User:
    """
    Require user to be verified (email confirmed).

    This dependency blocks unverified users from accessing protected endpoints like:
    - Enrichment API
    - DSAR (Data Subject Access Requests)
    - Any other feature requiring email verification

    Args:
        user: Current authenticated user

    Returns:
        Verified User object

    Raises:
        HTTPException: 403 if user not verified
    """
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Please check your email and verify your account.",
        )
    return user


# Type alias for dependency injection
VerifiedUser = Annotated[User, Depends(require_verified_user)]
