"""Feature flag list/upsert endpoints (§8.15)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import repository, service
from app.modules.admin.models import FeatureFlag
from app.modules.admin.permissions import require_permission
from app.modules.admin.schemas import FeatureFlagResponse, UpsertFeatureFlagRequest

router = APIRouter(
    prefix="/api/admin/feature-flags", tags=["admin"], route_class=EnvelopeAPIRoute
)


def _to_response(flag: FeatureFlag) -> FeatureFlagResponse:
    return FeatureFlagResponse(
        key=flag.key,
        enabled=flag.enabled,
        value=flag.value,
        description=flag.description,
        updated_by=flag.updated_by,
        updated_at=flag.updated_at,
    )


@router.get("", response_model=list[FeatureFlagResponse])
async def list_feature_flags(
    _user: User = Depends(require_permission("feature_flags", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> list[FeatureFlagResponse]:
    flags = await repository.list_feature_flags(db)
    return [_to_response(flag) for flag in flags]


@router.put("/{key}", response_model=FeatureFlagResponse)
async def upsert_feature_flag(
    key: str,
    payload: UpsertFeatureFlagRequest,
    request: Request,
    current_user: User = Depends(require_permission("feature_flags", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> FeatureFlagResponse:
    flag = await service.upsert_feature_flag(
        db,
        actor_id=current_user.id,
        key=key,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    return _to_response(flag)
