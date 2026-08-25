"""Business-logic layer for role/permission CRUD, following the exact
audit-logging pattern established by `service.py`'s `assign_role` (every
mutation calls `record_admin_action()` explicitly — Decision 2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin import repository
from app.modules.admin.audit import record_admin_action
from app.modules.admin.models import Role


async def create_role(
    db: AsyncSession, *, actor_id: UUID, name: str, description: str | None
) -> Role:
    """Create a new (non-system) role. Cannot create is_system=True roles via
    this path — system roles only come from migrations, per Role.is_system's
    docstring intent in models.py."""
    role = await repository.create_role(db, name=name, description=description)
    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action="role.create",
        target_type="role",
        target_id=str(role.id),
        before=None,
        after={"name": role.name, "description": role.description},
    )
    await db.commit()
    return role


async def attach_permission_to_role(
    db: AsyncSession, *, actor_id: UUID, role_id: UUID, permission_id: UUID
) -> None:
    role = await repository.get_role_by_id(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles' permissions cannot be modified at runtime",
        )
    await repository.attach_permission(db, role_id=role_id, permission_id=permission_id)
    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action="role.attach_permission",
        target_type="role",
        target_id=str(role_id),
        before=None,
        after={"permission_id": str(permission_id)},
    )
    await db.commit()


async def detach_permission_from_role(
    db: AsyncSession, *, actor_id: UUID, role_id: UUID, permission_id: UUID
) -> None:
    role = await repository.get_role_by_id(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles' permissions cannot be modified at runtime",
        )
    await repository.detach_permission(db, role_id=role_id, permission_id=permission_id)
    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action="role.detach_permission",
        target_type="role",
        target_id=str(role_id),
        before={"permission_id": str(permission_id)},
        after=None,
    )
    await db.commit()
