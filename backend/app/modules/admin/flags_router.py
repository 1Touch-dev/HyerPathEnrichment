"""Feature flag list/upsert endpoints (§8.15)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import repository, service
from app.modules.admin.models import FeatureFlag
from app.modules.admin.permissions import require_permission
from app.modules.admin.privileged_operations import assert_operation_available
from app.modules.admin.schemas import FeatureFlagResponse

router = APIRouter(prefix="/api/admin/feature-flags", tags=["admin"], route_class=EnvelopeAPIRoute)


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


@router.put(
    "/{key}",
    response_model=None,
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    responses={
        status.HTTP_405_METHOD_NOT_ALLOWED: {"description": "Feature flag mutations are disabled"}
    },
)
async def upsert_feature_flag(
    key: str,
    _user: User = Depends(require_permission("feature_flags", "write")),
) -> None:
    del key
    assert_operation_available("feature_flags.mutate")
    await service.reject_feature_flag_mutation()


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    responses={
        status.HTTP_405_METHOD_NOT_ALLOWED: {"description": "Feature flag mutations are disabled"}
    },
)
async def create_feature_flag(
    _user: User = Depends(require_permission("feature_flags", "write")),
) -> None:
    assert_operation_available("feature_flags.mutate")
    await service.reject_feature_flag_mutation()


@router.patch(
    "/{key}",
    response_model=None,
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    responses={
        status.HTTP_405_METHOD_NOT_ALLOWED: {"description": "Feature flag mutations are disabled"}
    },
)
async def toggle_feature_flag(
    key: str,
    _user: User = Depends(require_permission("feature_flags", "write")),
) -> None:
    del key
    assert_operation_available("feature_flags.mutate")
    await service.reject_feature_flag_mutation()


@router.delete(
    "/{key}",
    response_model=None,
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    responses={
        status.HTTP_405_METHOD_NOT_ALLOWED: {"description": "Feature flag mutations are disabled"}
    },
)
async def delete_feature_flag(
    key: str,
    _user: User = Depends(require_permission("feature_flags", "write")),
) -> None:
    del key
    assert_operation_available("feature_flags.mutate")
    await service.reject_feature_flag_mutation()
