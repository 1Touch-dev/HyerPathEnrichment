"""Service layer for the human-in-the-loop LinkedIn send task queue and the
operator-triggered automated-batch mode. See linkedin_send_models.py's module
docstring and 06-linkedin-outreach-send.md for the legal-risk rationale.

Do not import from app.integrations.linkedin.client or
app.integrations.multilogin.profile_pool anywhere in this module."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.suppression import check_suppression
from app.modules.outreach.linkedin_send_models import LinkedInSendBatch, LinkedInSendTask
from app.modules.outreach.models import OutreachMessage
from app.workers.queue import QUEUE_LINKEDIN_SEND_BATCH, get_redis_connection


async def enqueue_send_task(
    db: AsyncSession,
    *,
    outreach_message_id: UUID,
    linkedin_profile_url: str,
    action_type: str,
) -> LinkedInSendTask:
    """Called from OutreachService.send_message() instead of that method's email
    footer-append-and-mark-sent logic, only when message.message_type == 'linkedin'.
    Reuses app.compliance.suppression.check_suppression directly (conceptually the
    same suppression pattern as 05's email flow, keyed on the profile URL identifier
    instead of an email address) — raises 403 and does not enqueue if suppressed."""
    if await check_suppression(db, linkedin_profile_url):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This recipient has opted out of outreach and cannot be messaged",
        )

    task = LinkedInSendTask(
        outreach_message_id=outreach_message_id,
        linkedin_profile_url=linkedin_profile_url,
        action_type=action_type,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def list_tasks_for_operator(
    db: AsyncSession, *, statuses: list[str] | None = None
) -> list[LinkedInSendTask]:
    """Shared queue, not per-operator ownership — any operator with linkedin_tasks:operate
    can see and claim any pending/claimed task, mirroring linkedin_sourcing's shared-queue
    listing (no per-user filter there either)."""
    query = select(LinkedInSendTask).order_by(LinkedInSendTask.created_at.asc())
    if statuses:
        query = query.where(LinkedInSendTask.status.in_(statuses))
    else:
        query = query.where(LinkedInSendTask.status.in_(["pending", "claimed"]))
    result = await db.execute(query)
    return list(result.scalars().all())


async def _get_task_or_404(db: AsyncSession, task_id: UUID) -> LinkedInSendTask:
    result = await db.execute(select(LinkedInSendTask).where(LinkedInSendTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


async def claim_task(db: AsyncSession, *, task_id: UUID, operator_id: UUID) -> LinkedInSendTask:
    task = await _get_task_or_404(db, task_id)
    if task.status == "claimed" and task.claimed_by != operator_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Task already claimed by another operator"
        )
    if task.status not in ("pending", "claimed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task cannot be claimed from status '{task.status}'",
        )
    task.status = "claimed"
    task.claimed_by = operator_id
    task.claimed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(task)
    return task


async def complete_task(
    db: AsyncSession, *, task_id: UUID, operator_id: UUID, outcome_note: str | None
) -> LinkedInSendTask:
    """Also updates the parent OutreachMessage to status='sent' — a LinkedIn-type
    message is not 'sent' merely because a task was created, only when a human
    operator confirms they performed the action themselves."""
    task = await _get_task_or_404(db, task_id)
    if task.status not in ("pending", "claimed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task cannot be completed from status '{task.status}'",
        )
    task.status = "completed"
    task.completed_at = datetime.now(UTC)
    task.outcome_note = outcome_note
    if task.claimed_by is None:
        task.claimed_by = operator_id
        task.claimed_at = task.claimed_at or datetime.now(UTC)

    message_result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.id == task.outreach_message_id)
    )
    message = message_result.scalar_one_or_none()
    if message is not None:
        message.status = "sent"
        message.sent_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(task)
    return task


async def skip_task(
    db: AsyncSession, *, task_id: UUID, operator_id: UUID, outcome_note: str | None
) -> LinkedInSendTask:
    """Parent OutreachMessage.status stays 'draft' — not sent, not failed; the
    candidate can re-request a draft or try a different approach."""
    task = await _get_task_or_404(db, task_id)
    if task.status not in ("pending", "claimed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task cannot be skipped from status '{task.status}'",
        )
    task.status = "skipped"
    task.outcome_note = outcome_note
    if task.claimed_by is None:
        task.claimed_by = operator_id
        task.claimed_at = task.claimed_at or datetime.now(UTC)
    await db.commit()
    await db.refresh(task)
    return task


async def create_batch(
    db: AsyncSession,
    *,
    triggered_by: UUID,
    multilogin_profile_id: str,
    max_sends_per_day: int,
    task_ids: list[UUID],
) -> LinkedInSendBatch:
    """`max_sends_per_day` is a required Pydantic field on the request schema (422
    without it) — this function additionally re-validates it's a positive int, since
    it's also reachable directly (e.g. from tests) without going through the schema."""
    if max_sends_per_day <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_sends_per_day must be a positive integer",
        )

    batch = LinkedInSendBatch(
        triggered_by=triggered_by,
        multilogin_profile_id=multilogin_profile_id,
        max_sends_per_day=max_sends_per_day,
    )
    db.add(batch)
    await db.flush()

    if task_ids:
        result = await db.execute(select(LinkedInSendTask).where(LinkedInSendTask.id.in_(task_ids)))
        tasks = list(result.scalars().all())
        found_ids = {task.id for task in tasks}
        missing = [str(tid) for tid in task_ids if tid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task(s) not found: {', '.join(missing)}",
            )
        for task in tasks:
            if task.batch_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Task {task.id} is already attached to another batch",
                )
            task.batch_id = batch.id

    await db.commit()
    await db.refresh(batch)
    return batch


async def start_batch(
    db: AsyncSession, *, batch_id: UUID, redis_conn: Redis | None = None
) -> LinkedInSendBatch:
    """Sets status='running' and started_at — a separate human action from
    create_batch, per this chunk's human-trigger design. Enqueues
    app.workers.tasks.linkedin_send_batch.run_linkedin_send_batch_job, which enforces
    max_sends_per_day; it does not itself perform any LinkedIn action."""
    result = await db.execute(select(LinkedInSendBatch).where(LinkedInSendBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if batch.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batch cannot be started from status '{batch.status}'",
        )
    batch.status = "running"
    batch.started_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(batch)

    conn = redis_conn or get_redis_connection()
    queue = Queue(QUEUE_LINKEDIN_SEND_BATCH, connection=conn)
    queue.enqueue(
        "app.workers.tasks.linkedin_send_batch.run_linkedin_send_batch_job",
        str(batch.id),
    )
    return batch
