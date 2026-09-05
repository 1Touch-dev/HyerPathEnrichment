"""FastAPI router for the LinkedIn send task queue (manual mode) and the
operator-triggered automated-batch mode. Gated behind linkedin_tasks:operate.
See linkedin_send_models.py's module docstring for the legal-risk rationale."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.permissions import require_permission
from app.modules.outreach import linkedin_send_service
from app.modules.outreach.linkedin_send_models import LinkedInSendBatch, LinkedInSendTask
from app.modules.outreach.linkedin_send_schemas import (
    CompleteLinkedInTaskRequest,
    CreateLinkedInSendBatchRequest,
    LinkedInSendBatchResponse,
    LinkedInSendTaskResponse,
    LinkedInTaskListResponse,
    SkipLinkedInTaskRequest,
)

router = APIRouter(prefix="/api/outreach", tags=["linkedin-tasks"], route_class=EnvelopeAPIRoute)


def _task_to_response(task: LinkedInSendTask) -> LinkedInSendTaskResponse:
    return LinkedInSendTaskResponse(
        id=str(task.id),
        outreach_message_id=str(task.outreach_message_id),
        batch_id=str(task.batch_id) if task.batch_id else None,
        linkedin_profile_url=task.linkedin_profile_url,
        action_type=task.action_type,  # type: ignore[arg-type]
        status=task.status,  # type: ignore[arg-type]
        claimed_by=str(task.claimed_by) if task.claimed_by else None,
        claimed_at=task.claimed_at,
        completed_at=task.completed_at,
        outcome_note=task.outcome_note,
        created_at=task.created_at,
    )


def _batch_to_response(batch: LinkedInSendBatch) -> LinkedInSendBatchResponse:
    return LinkedInSendBatchResponse(
        id=str(batch.id),
        triggered_by=str(batch.triggered_by) if batch.triggered_by else None,
        multilogin_profile_id=batch.multilogin_profile_id,
        status=batch.status,  # type: ignore[arg-type]
        max_sends_per_day=batch.max_sends_per_day,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        created_at=batch.created_at,
    )


@router.get("/linkedin-tasks", response_model=LinkedInTaskListResponse)
async def list_linkedin_tasks(
    _user: User = Depends(require_permission("linkedin_tasks", "operate")),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db_session),
) -> LinkedInTaskListResponse:
    statuses = [status_filter] if status_filter else None
    tasks = await linkedin_send_service.list_tasks_for_operator(db, statuses=statuses)
    return LinkedInTaskListResponse(tasks=[_task_to_response(t) for t in tasks])


@router.post("/linkedin-tasks/{task_id}/claim", response_model=LinkedInSendTaskResponse)
async def claim_linkedin_task(
    task_id: UUID,
    current_user: User = Depends(require_permission("linkedin_tasks", "operate")),
    db: AsyncSession = Depends(get_db_session),
) -> LinkedInSendTaskResponse:
    task = await linkedin_send_service.claim_task(db, task_id=task_id, operator_id=current_user.id)
    return _task_to_response(task)


@router.post("/linkedin-tasks/{task_id}/complete", response_model=LinkedInSendTaskResponse)
async def complete_linkedin_task(
    task_id: UUID,
    body: CompleteLinkedInTaskRequest,
    current_user: User = Depends(require_permission("linkedin_tasks", "operate")),
    db: AsyncSession = Depends(get_db_session),
) -> LinkedInSendTaskResponse:
    task = await linkedin_send_service.complete_task(
        db, task_id=task_id, operator_id=current_user.id, outcome_note=body.outcome_note
    )
    return _task_to_response(task)


@router.post("/linkedin-tasks/{task_id}/skip", response_model=LinkedInSendTaskResponse)
async def skip_linkedin_task(
    task_id: UUID,
    body: SkipLinkedInTaskRequest,
    current_user: User = Depends(require_permission("linkedin_tasks", "operate")),
    db: AsyncSession = Depends(get_db_session),
) -> LinkedInSendTaskResponse:
    task = await linkedin_send_service.skip_task(
        db, task_id=task_id, operator_id=current_user.id, outcome_note=body.outcome_note
    )
    return _task_to_response(task)


@router.post("/linkedin-send-batches", response_model=LinkedInSendBatchResponse)
async def create_linkedin_send_batch(
    body: CreateLinkedInSendBatchRequest,
    current_user: User = Depends(require_permission("linkedin_tasks", "operate")),
    db: AsyncSession = Depends(get_db_session),
) -> LinkedInSendBatchResponse:
    batch = await linkedin_send_service.create_batch(
        db,
        triggered_by=current_user.id,
        multilogin_profile_id=body.multilogin_profile_id,
        max_sends_per_day=body.max_sends_per_day,
        task_ids=body.task_ids,
    )
    return _batch_to_response(batch)


@router.post("/linkedin-send-batches/{batch_id}/start", response_model=LinkedInSendBatchResponse)
async def start_linkedin_send_batch(
    batch_id: UUID,
    _user: User = Depends(require_permission("linkedin_tasks", "operate")),
    db: AsyncSession = Depends(get_db_session),
) -> LinkedInSendBatchResponse:
    batch = await linkedin_send_service.start_batch(db, batch_id=batch_id)
    return _batch_to_response(batch)
