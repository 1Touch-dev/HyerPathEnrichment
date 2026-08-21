"""Role listing endpoint (§8.15)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import repository
from app.modules.admin.permissions import require_permission
from app.modules.admin.schemas import PermissionResponse, RoleWithPermissionsResponse

router = APIRouter(prefix="/api/admin/roles", tags=["admin"], route_class=EnvelopeAPIRoute)


@router.get("", response_model=list[RoleWithPermissionsResponse])
async def list_roles(
    _user: User = Depends(require_permission("roles", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> list[RoleWithPermissionsResponse]:
    roles = await repository.list_roles(db)
    return [
        RoleWithPermissionsResponse(
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
        for role in roles
    ]
