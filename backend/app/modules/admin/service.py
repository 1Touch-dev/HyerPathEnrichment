"""Service layer for the Admin Module. Every mutation here calls
record_admin_action() explicitly (Decision 2) — the fallback middleware only
catches what this layer misses."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.errors import AppError
from app.modules.admin import repository
from app.modules.admin.audit import record_admin_action
from app.modules.admin.schemas import (
    AdminUserResponse,
    UpsertFeatureFlagRequest,
)


def _user_to_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_superuser=user.is_superuser,
        role_id=user.role_id,
        role_name=user.role.name if user.role else None,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
        deleted_at=user.deleted_at,
    )


async def list_users_paginated(
    db: AsyncSession, *, cursor: str | None, limit: int, is_active: bool | None
) -> tuple[list[AdminUserResponse], str | None, bool]:
    rows, next_cursor, has_more = await repository.list_users(
        db, cursor=cursor, limit=limit, is_active=is_active
    )
    return [_user_to_response(u) for u in rows], next_cursor, has_more


async def update_user_status(
    db: AsyncSession,
    *,
    actor_id: UUID,
    target_user_id: UUID,
    is_active: bool,
    reason: str | None,
    ip_address: str | None,
) -> AdminUserResponse:
    user = await stage_user_status_update(
        db,
        actor_id=actor_id,
        target_user_id=target_user_id,
        is_active=is_active,
        reason=reason,
        ip_address=ip_address,
    )
    await db.commit()
    return _user_to_response(user)


async def stage_user_status_update(
    db: AsyncSession,
    *,
    actor_id: UUID,
    target_user_id: UUID,
    is_active: bool,
    reason: str | None,
    ip_address: str | None,
) -> User:
    user = await repository.get_user_by_id(db, target_user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if user.is_superuser and not is_active:
        actor = await repository.get_user_by_id(db, actor_id)
        if actor is None or not actor.is_superuser:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only a superuser can deactivate another superuser",
            )

    before = {"is_active": user.is_active}
    user.is_active = is_active
    await db.flush()
    after = {"is_active": user.is_active, "reason": reason}

    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action="user.status_changed",
        target_type="user",
        target_id=str(target_user_id),
        before=before,
        after=after,
        ip_address=ip_address,
    )
    return user


async def assign_role(
    db: AsyncSession,
    *,
    actor_id: UUID,
    target_user_id: UUID,
    role_id: UUID | None,
    ip_address: str | None,
) -> AdminUserResponse:
    user = await stage_role_assignment(
        db,
        actor_id=actor_id,
        target_user_id=target_user_id,
        role_id=role_id,
        ip_address=ip_address,
    )
    await db.commit()
    return _user_to_response(user)


async def stage_role_assignment(
    db: AsyncSession,
    *,
    actor_id: UUID,
    target_user_id: UUID,
    role_id: UUID | None,
    ip_address: str | None,
) -> User:
    """Stage a role change and its audit row without committing the caller's transaction."""
    user = await repository.get_user_by_id(db, target_user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    before = {"role_id": str(user.role_id) if user.role_id else None}
    user.role_id = role_id
    await db.flush()
    await db.refresh(user, attribute_names=["role"])
    after = {"role_id": str(role_id) if role_id else None}

    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action="user.role_changed",
        target_type="user",
        target_id=str(target_user_id),
        before=before,
        after=after,
        ip_address=ip_address,
    )
    return user


async def upsert_feature_flag(
    db: AsyncSession,
    *,
    actor_id: UUID,
    key: str,
    payload: UpsertFeatureFlagRequest,
    ip_address: str | None,
) -> None:
    del db, actor_id, key, payload, ip_address
    await reject_feature_flag_mutation()


async def reject_feature_flag_mutation() -> None:
    raise AppError(
        code="FEATURE_FLAGS_READ_ONLY",
        message="Feature flag mutation is disabled until an application consumer exists.",
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    )
