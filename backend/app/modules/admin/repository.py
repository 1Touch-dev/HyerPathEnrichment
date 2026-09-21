"""Data access for the Admin Module. Routes/services call these; no ORM query
lives directly in router.py, per RULE.md 'routes are thin'."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.modules.admin.models import AdminAuditLog, FeatureFlag, Permission, Role, RolePermission
from app.modules.admin.pagination import decode_cursor, encode_cursor


async def list_users(
    db: AsyncSession, *, cursor: str | None, limit: int, is_active: bool | None = None
) -> tuple[list[User], str | None, bool]:
    query = (
        select(User)
        .options(selectinload(User.role))
        .order_by(User.created_at.desc(), User.id.desc())
    )
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (User.created_at < created_at)
            | ((User.created_at == created_at) & (User.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return rows, next_cursor, has_more


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def list_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(select(Role).options(selectinload(Role.permissions)))
    return list(result.scalars().all())


async def create_role(db: AsyncSession, *, name: str, description: str | None) -> Role:
    role = Role(id=uuid4(), name=name, description=description, is_system=False)
    db.add(role)
    await db.flush()
    return role


async def create_permission(
    db: AsyncSession, *, resource: str, action: str, description: str | None
) -> Permission:
    permission = Permission(id=uuid4(), resource=resource, action=action, description=description)
    db.add(permission)
    await db.flush()
    return permission


async def attach_permission(db: AsyncSession, *, role_id: UUID, permission_id: UUID) -> None:
    db.add(RolePermission(role_id=role_id, permission_id=permission_id))
    await db.flush()


async def detach_permission(db: AsyncSession, *, role_id: UUID, permission_id: UUID) -> None:
    await db.execute(
        delete(RolePermission).where(
            RolePermission.role_id == role_id, RolePermission.permission_id == permission_id
        )
    )
    await db.flush()


async def get_role_by_id(db: AsyncSession, role_id: UUID) -> Role | None:
    # populate_existing=True: callers use this to read the authoritative post-mutation
    # state (e.g. right after attach_permission/detach_permission commit a raw
    # role_permissions insert/delete that doesn't go through the viewonly
    # `Role.permissions` relationship) — without it, an already-identity-mapped Role
    # instance's selectinload'ed `permissions` collection would stay stale for the
    # rest of the session.
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def list_audit_logs(
    db: AsyncSession, *, cursor: str | None, limit: int, action: str | None = None
) -> tuple[list[AdminAuditLog], str | None, bool]:
    query = select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
    if action:
        query = query.where(AdminAuditLog.action == action)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (AdminAuditLog.created_at < created_at)
            | ((AdminAuditLog.created_at == created_at) & (AdminAuditLog.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return rows, next_cursor, has_more


async def list_feature_flags(db: AsyncSession) -> list[FeatureFlag]:
    result = await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))
    return list(result.scalars().all())


async def get_feature_flag(db: AsyncSession, key: str) -> FeatureFlag | None:
    result = await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    return result.scalar_one_or_none()


async def count_active_users(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(User).where(User.is_active.is_(True))
    )
    return int(result.scalar_one())
