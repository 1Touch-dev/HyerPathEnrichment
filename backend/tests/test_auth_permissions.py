"""Tests for app.auth.permissions.require_verified_user."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth.models import User
from app.auth.permissions import require_verified_user


def _make_user(*, is_verified: bool) -> User:
    return User(
        email="permissions-test@example.com",
        first_name="Test",
        last_name="User",
        is_verified=is_verified,
    )


@pytest.mark.asyncio
async def test_require_verified_user_allows_verified_user() -> None:
    user = _make_user(is_verified=True)

    result = await require_verified_user(user=user)

    assert result is user


@pytest.mark.asyncio
async def test_require_verified_user_rejects_unverified_user() -> None:
    user = _make_user(is_verified=False)

    with pytest.raises(HTTPException) as exc_info:
        await require_verified_user(user=user)

    assert exc_info.value.status_code == 403
    assert "verification required" in exc_info.value.detail.lower()
