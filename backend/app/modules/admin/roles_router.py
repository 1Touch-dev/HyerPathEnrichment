"""Role listing + CRUD endpoints (§8.15; create/attach/detach added by
machine-2-parallel-tracks/04-rbac-admin-platform.md)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import repository, roles_service
from app.modules.admin.models import Role
from app.modules.admin.permissions import require_permission
from app.modules.admin.schemas import (
    AttachPermissionRequest,
    CreateRoleRequest,
    PermissionResponse,
    RoleWithPermissionsResponse,
)

router = APIRouter(prefix="/api/admin/roles", tags=["admin"], route_class=EnvelopeAPIRoute)


def _role_to_response(role: Role) -> RoleWithPermissionsResponse:
    return RoleWithPermissionsResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            PermissionResponse(
                id=perm.id,
                resource=perm.resource,
                action=perm.action,
                description=perm.description,
            )
            for perm in role.permissions
        ],
    )


@router.get("", response_model=list[RoleWithPermissionsResponse])
async def list_roles(
    _user: User = Depends(require_permission("roles", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> list[RoleWithPermissionsResponse]:
    roles = await repository.list_roles(db)
    return [_role_to_response(role) for role in roles]


@router.post("", response_model=RoleWithPermissionsResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: CreateRoleRequest,
    user: User = Depends(require_permission("roles", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> RoleWithPermissionsResponse:
    role = await roles_service.create_role(
        db, actor_id=user.id, name=body.name, description=body.description
    )
    refreshed_role = await repository.get_role_by_id(db, role.id)
    if refreshed_role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role was created but could not be reloaded",
        )
    return _role_to_response(refreshed_role)


@router.post("/{role_id}/permissions", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def attach_permission(
    role_id: UUID,
    body: AttachPermissionRequest,
    user: User = Depends(require_permission("roles", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await roles_service.attach_permission_to_role(
        db, actor_id=user.id, role_id=role_id, permission_id=body.permission_id
    )


@router.delete(
    "/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def detach_permission(
    role_id: UUID,
    permission_id: UUID,
    user: User = Depends(require_permission("roles", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await roles_service.detach_permission_from_role(
        db, actor_id=user.id, role_id=role_id, permission_id=permission_id
    )
