"""RQ worker task: process a 'running' LinkedInSendBatch, enforcing max_sends_per_day
as a hard ceiling per multilogin_profile_id (halt at ceiling, resume next day).

This module does not import from or extend app.integrations.linkedin.client or
app.integrations.multilogin.profile_pool — the actual mechanism that would perform
an automated click on linkedin.com is an explicit, out-of-scope follow-up chunk
pending its own design decision/ADR (see 06-linkedin-outreach-send.md's "Track 06 —
updated scope" section and this module's _perform_send_action below). This job's
scope is the batch/queue/rate-limit data model and the human-trigger boundary only.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.database.orm_registry  # noqa: F401
from app.database.session import SessionLocal
from app.modules.outreach.linkedin_send_models import LinkedInSendBatch, LinkedInSendTask

logger = logging.getLogger(__name__)


class LinkedInSendNotImplementedError(RuntimeError):
    """Raised by _perform_send_action — the automated-click mechanism does not
    exist yet in this codebase (deliberate scope cut, see module docstring)."""


async def _sends_today_for_profile(session: AsyncSession, multilogin_profile_id: str) -> int:
    """Counts LinkedInSendTask rows completed today (UTC) whose parent batch uses
    this multilogin_profile_id — a hard per-profile-per-day ceiling spans every
    batch that ever used that profile, not just the batch currently running."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.count())
        .select_from(LinkedInSendTask)
        .join(LinkedInSendBatch, LinkedInSendTask.batch_id == LinkedInSendBatch.id)
        .where(
            LinkedInSendBatch.multilogin_profile_id == multilogin_profile_id,
            LinkedInSendTask.status == "completed",
            LinkedInSendTask.completed_at >= today_start,
        )
    )
    return int(result.scalar_one())


def _perform_send_action(task: LinkedInSendTask) -> None:
    """Placeholder for the actual automated-click mechanism. Deliberately not
    implemented — see module docstring. Always raises so this job never silently
    pretends a send happened; run_linkedin_send_batch_job below catches this and
    halts the batch run without marking any task complete or failed."""
    raise LinkedInSendNotImplementedError(
        "Automated LinkedIn send is not implemented — this is an explicit scope cut "
        "pending its own design decision/ADR (see 06-linkedin-outreach-send.md)"
    )


async def _run_linkedin_send_batch_job(batch_id: str) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(LinkedInSendBatch).where(LinkedInSendBatch.id == UUID(batch_id))
        )
        batch = result.scalar_one_or_none()
        if batch is None:
            logger.warning("LinkedInSendBatch not found", extra={"batch_id": batch_id})
            return
        if batch.status != "running":
            logger.info(
                "Batch is not in 'running' status; skipping",
                extra={"batch_id": batch_id, "status": batch.status},
            )
            return

        tasks_result = await session.execute(
            select(LinkedInSendTask)
            .where(LinkedInSendTask.batch_id == batch.id, LinkedInSendTask.status == "pending")
            .order_by(LinkedInSendTask.created_at.asc())
        )
        pending_tasks = list(tasks_result.scalars().all())

        sends_today = await _sends_today_for_profile(session, batch.multilogin_profile_id)

        for task in pending_tasks:
            if sends_today >= batch.max_sends_per_day:
                logger.info(
                    "Daily send ceiling reached for profile; halting until tomorrow",
                    extra={
                        "batch_id": batch_id,
                        "multilogin_profile_id": batch.multilogin_profile_id,
                        "max_sends_per_day": batch.max_sends_per_day,
                    },
                )
                break
            try:
                _perform_send_action(task)
            except LinkedInSendNotImplementedError:
                logger.warning(
                    "Automated LinkedIn send is not implemented; leaving task pending "
                    "for manual completion instead of marking it sent or failed",
                    extra={"batch_id": batch_id, "task_id": str(task.id)},
                )
                break

        await session.commit()


def run_linkedin_send_batch_job(batch_id: str) -> None:
    """Sync RQ entrypoint, mirroring generate_outreach_draft_job's asyncio.run wrapper."""
    asyncio.run(_run_linkedin_send_batch_job(batch_id))
