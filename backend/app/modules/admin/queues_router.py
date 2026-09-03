"""Authorized queue inspection; all queue mutations fail closed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.core.responses import ErrorResponse
from app.database.session import get_db_session
from app.modules.admin import queues_service
from app.modules.admin.permissions import require_permission, user_has_permission
from app.modules.admin.schemas import FailedJobResponse, QueuesOverviewResponse
from app.observability.security_metrics import record_authorization

router = APIRouter(prefix="/api/admin/queues", tags=["admin"], route_class=EnvelopeAPIRoute)


async def _require_queue_retry_permission(
    request: Request,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Keep denied retry attempts attributable before failing authorization."""
    request.state.user_id = user.id
    allowed = await user_has_permission(db, user, "queues", "retry")
    record_authorization("queue_retry", allowed=allowed)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing permission: queues:retry",
        )
    return user


@router.get("", response_model=QueuesOverviewResponse)
async def get_queues_overview(
    _user: User = Depends(require_permission("queues", "read")),
) -> QueuesOverviewResponse:
    return QueuesOverviewResponse(queues=queues_service.get_queues_overview())


@router.get("/{name}/failed", response_model=list[FailedJobResponse])
async def list_failed_jobs(
    name: str,
    limit: int = Query(default=50, ge=1, le=200),
    _user: User = Depends(require_permission("queues", "read")),
) -> list[FailedJobResponse]:
    return queues_service.list_failed_jobs(name, limit=limit)


@router.post(
    "/{name}/failed/{job_id}/retry",
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    response_model=None,
    responses={
        status.HTTP_405_METHOD_NOT_ALLOWED: {
            "model": ErrorResponse,
            "description": "Queue administration is read-only; retry is unavailable.",
        }
    },
)
async def retry_failed_job(
    name: str,
    job_id: str,
    _user: User = Depends(_require_queue_retry_permission),
) -> None:
    queues_service.deny_retry(name, job_id)
