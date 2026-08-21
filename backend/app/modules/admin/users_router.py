"""User management endpoints (§8.15). Routes are thin — auth/permission check,
call one service/repository function, return."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import service
from app.modules.admin.permissions import require_permission, require_superuser_strict
from app.modules.admin.schemas import (
    AdminUserListResponse,
    AdminUserResponse,
    AssignRoleRequest,
    UpdateUserStatusRequest,
)

router = APIRouter(prefix="/api/admin/users", tags=["admin"], route_class=EnvelopeAPIRoute)


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    _user: User = Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserListResponse:
    items, next_cursor, has_more = await service.list_users_paginated(
        db, cursor=cursor, limit=limit, is_active=is_active
    )
    return AdminUserListResponse(items=items, next_cursor=next_cursor, has_more=has_more)


@router.patch("/{user_id}/status", response_model=AdminUserResponse)
async def update_user_status(
    user_id: UUID,
    payload: UpdateUserStatusRequest,
    request: Request,
    current_user: User = Depends(require_permission("users", "suspend")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    return await service.update_user_status(
        db,
        actor_id=current_user.id,
        target_user_id=user_id,
        is_active=payload.is_active,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )


@router.put("/{user_id}/role", response_model=AdminUserResponse)
async def assign_role(
    user_id: UUID,
    payload: AssignRoleRequest,
    request: Request,
    current_user: User = Depends(require_superuser_strict),
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    return await service.assign_role(
        db,
        actor_id=current_user.id,
        target_user_id=user_id,
        role_id=payload.role_id,
        ip_address=get_client_ip(request),
    )
