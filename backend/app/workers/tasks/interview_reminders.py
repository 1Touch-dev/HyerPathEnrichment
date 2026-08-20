"""RQ worker task: send the interview reminder email+push (Module 4, Module D §8.6).

Enqueued once, at schedule-creation time, via `app.workers.queue.
enqueue_interview_reminder`. Re-checks `reminder_sent_at is None` (idempotency
guard) and re-fetches the current `scheduled_at`/`InterviewSchedule` row rather
than trusting the enqueue-time snapshot — the interview may have been
rescheduled or cancelled between enqueue and this job actually running.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

# Import ORM registry FIRST to register all models with SQLAlchemy
import app.database.orm_registry  # noqa: F401
from app.auth.models import User
from app.database.session import SessionLocal, engine
from app.infrastructure.redis import close_redis
from app.modules.interview_scheduling.ics_builder import build_google_calendar_link
from app.modules.interview_scheduling.models import InterviewSchedule
from app.modules.interview_scheduling.repository import mark_reminder_sent
from app.modules.job_matching import push
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.job_matching.repository import list_subscriptions_for_user
from app.observability.interview_scheduling_metrics import interview_reminders_sent_total
from app.services.email_service import EmailTemplate, get_email_service

logger = logging.getLogger(__name__)


def send_interview_reminder_job(interview_schedule_id: str) -> None:
    """RQ entrypoint (sync)."""
    asyncio.run(_send_interview_reminder_job_async(interview_schedule_id))


async def _send_interview_reminder_job_async(interview_schedule_id: str) -> None:
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                select(InterviewSchedule, JobMatch, JobPosting)
                .join(JobMatch, InterviewSchedule.job_match_id == JobMatch.id)
                .outerjoin(JobPosting, JobMatch.job_posting_id == JobPosting.id)
                .where(InterviewSchedule.id == UUID(interview_schedule_id))
            )
            row = result.first()
            if row is None:
                logger.info(
                    "Interview schedule not found (likely cancelled) — skipping reminder",
                    extra={"interview_schedule_id": interview_schedule_id},
                )
                return
            schedule, match, posting = row

            # Idempotency guard: a duplicate enqueue or an RQ retry must never
            # double-send the reminder.
            if schedule.reminder_sent_at is not None:
                logger.info(
                    "Reminder already sent — skipping",
                    extra={"interview_schedule_id": interview_schedule_id},
                )
                return

            user = await session.get(User, schedule.user_id)
            if user is None:
                logger.warning(
                    "User not found for interview schedule — skipping reminder",
                    extra={"interview_schedule_id": interview_schedule_id},
                )
                return

            title = posting.title if posting else "your role"
            company = posting.company if posting else "the company"
            # Re-fetched schedule.scheduled_at above (not a stale enqueue-time
            # snapshot) — a reschedule between enqueue and this job running is
            # reflected here automatically since we always read the current row.
            await get_email_service().send_template(
                EmailTemplate.INTERVIEW_REMINDER,
                recipient=user.email,
                context={
                    "title": title,
                    "company": company,
                    "scheduled_at": schedule.scheduled_at.isoformat(),
                    "ics_download_url": f"/api/interviews/matches/{match.id}/schedule.ics",
                    "google_calendar_link": build_google_calendar_link(
                        summary=f"Interview: {title} at {company}",
                        description=schedule.notes or "",
                        location=None,
                        start=schedule.scheduled_at,
                        duration_minutes=schedule.duration_minutes,
                    ),
                },
            )
            subs = await list_subscriptions_for_user(session, user.id)
            for sub in subs:
                await push.send_push_notification(
                    sub,
                    {
                        "event": "interview_reminder",
                        "title": title,
                        "company": company,
                        "scheduled_at": schedule.scheduled_at.isoformat(),
                    },
                )

            await mark_reminder_sent(session, schedule.id)
            interview_reminders_sent_total.inc()

            logger.info(
                "Interview reminder sent",
                extra={"interview_schedule_id": interview_schedule_id},
            )
    finally:
        await close_redis()
        await engine.dispose()
