"""User management endpoints (§8.15). Routes are thin — auth/permission check,
call one service/repository function, return."""

from __future__ import annotations

from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import service
from app.modules.admin.permissions import require_permission, require_superuser_strict
from app.modules.admin.privileged_operations import (
    assert_operation_available,
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    operation_for_user_status,
    require_idempotency_key,
)
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
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("users", "suspend")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    operation_id = operation_for_user_status(is_active=payload.is_active)
    assert_operation_available(operation_id)
    normalized_key = require_idempotency_key(operation_id, idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id=operation_id,
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {
                "user_id": user_id,
                "is_active": payload.is_active,
                "reason": payload.reason,
            }
        ),
    )
    if replay is not None:
        return AdminUserResponse.model_validate(replay.response_body["user"])

    user = await service.stage_user_status_update(
        db,
        actor_id=current_user.id,
        target_user_id=user_id,
        is_active=payload.is_active,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"user": AdminUserResponse.model_validate(user).model_dump(mode="json")},
        )
        await db.commit()
    return AdminUserResponse.model_validate(user)


@router.put("/{user_id}/role", response_model=AdminUserResponse)
async def assign_role(
    user_id: UUID,
    payload: AssignRoleRequest,
    request: Request,
    current_user: User = Depends(require_superuser_strict),
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    assert_operation_available("user.role.assign")
    return await service.assign_role(
        db,
        actor_id=current_user.id,
        target_user_id=user_id,
        role_id=payload.role_id,
        ip_address=get_client_ip(request),
    )
