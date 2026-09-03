"""RBAC permission dependency. Additive to `require_superuser` — see Decision 1.
Not to be confused with `app/auth/permissions.py` (unrelated file, see §5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.auth.models import User
from app.database.session import get_db_session
from app.modules.admin.models import Permission, RolePermission


def user_is_staff(user: User) -> bool:
    """Return whether the user may cross the shared staff product door."""
    return user.is_superuser or user.role_id is not None


def require_staff(user: VerifiedUser) -> User:
    """Require a verified user assigned to staff or marked as a superuser."""
    if not user_is_staff(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required",
        )
    return user


async def user_has_permission(db: AsyncSession, user: User, resource: str, action: str) -> bool:
    """`is_superuser` short-circuits to True with no DB lookup (Decision 1).
    Otherwise checks user.role_id -> RolePermission -> Permission(resource, action)."""
    if user.is_superuser:
        return True
    if user.role_id is None:
        return False

    result = await db.execute(
        select(Permission.id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(
            RolePermission.role_id == user.role_id,
            Permission.resource == resource,
            Permission.action == action,
        )
    )
    return result.scalar_one_or_none() is not None


def require_permission(resource: str, action: str) -> Callable[..., Any]:
    """FastAPI dependency factory: `Depends(require_permission("users", "suspend"))`."""

    async def _check(user: VerifiedUser, db: AsyncSession = Depends(get_db_session)) -> User:
        if not await user_has_permission(db, user, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {resource}:{action}",
            )
        return user

    return _check


def require_superuser_strict(user: VerifiedUser) -> User:
    """For the handful of actions Decision 1 keeps as `is_superuser`-only forever
    (role management itself) — RBAC cannot grant the ability to grant roles."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user
