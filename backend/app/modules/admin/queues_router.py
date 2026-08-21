"""RQ queue introspection + retry endpoints (§8.15). `queues_service` functions
are synchronous (rq's client is sync) — called directly, no `await`, matching
how the module itself is written."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.modules.admin import queues_service
from app.modules.admin.permissions import require_permission
from app.modules.admin.schemas import FailedJobResponse, QueuesOverviewResponse

router = APIRouter(prefix="/api/admin/queues", tags=["admin"], route_class=EnvelopeAPIRoute)


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


@router.post("/{name}/failed/{job_id}/retry", status_code=status.HTTP_204_NO_CONTENT)
async def retry_failed_job(
    name: str,
    job_id: str,
    _user: User = Depends(require_permission("queues", "retry")),
) -> None:
    requeued = queues_service.retry_failed_job(name, job_id)
    if not requeued:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Failed job not found")
