"""RBAC permission dependency. Additive to `require_superuser` — see Decision 1.
Not to be confused with `app/auth/permissions.py` (unrelated file, see §5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.auth.models import User
from app.database.session import get_db_session
from app.modules.admin.models import Permission, RolePermission
from app.observability.security_metrics import record_authorization


def user_is_staff(user: User) -> bool:
    """Return whether the user may cross the shared staff product door."""
    return user.is_superuser or user.role_id is not None


def require_staff(request: Request, user: VerifiedUser) -> User:
    """Require a verified user assigned to staff or marked as a superuser."""
    request.state.user_id = user.id
    allowed = user_is_staff(user)
    record_authorization("staff", allowed=allowed)
    if not allowed:
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

    role_id_key = user.role_id.hex
    role_permission_role_id = func.replace(cast(RolePermission.role_id, String), "-", "")
    permission_id_column = func.replace(cast(Permission.id, String), "-", "")
    role_permission_permission_id = func.replace(
        cast(RolePermission.permission_id, String), "-", ""
    )
    result = await db.execute(
        select(Permission.id)
        .join(RolePermission, role_permission_permission_id == permission_id_column)
        .where(
            role_permission_role_id == role_id_key,
            Permission.resource == resource,
            Permission.action == action,
        )
    )
    return result.scalar_one_or_none() is not None


def require_permission(resource: str, action: str) -> Callable[..., Any]:
    """FastAPI dependency factory: `Depends(require_permission("users", "suspend"))`."""

    async def _check(
        request: Request,
        user: VerifiedUser,
        db: AsyncSession = Depends(get_db_session),
    ) -> User:
        request.state.user_id = user.id
        allowed = await user_has_permission(db, user, resource, action)
        record_authorization("permission", allowed=allowed)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {resource}:{action}",
            )
        return user

    return _check


def require_superuser_strict(user: VerifiedUser) -> User:
    """For the handful of actions Decision 1 keeps as `is_superuser`-only forever
    (role management itself) — RBAC cannot grant the ability to grant roles."""
    record_authorization("superuser", allowed=user.is_superuser)
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user
