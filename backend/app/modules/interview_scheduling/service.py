"""Service-layer helpers for interview scheduling: response mapping and the
confirmation-notification fan-out reused by the router (Module 4, Module D §8.3/§8.5).

Note: the plan's illustrative `email_service.send_email(db, user, ...)` and
`push.get_subscriptions_for_user(...)` calls don't exist verbatim on this
codebase's actual `EmailService`/`job_matching` modules — adapted here to the
real APIs (`EmailService.send_template`, `job_matching.repository.
list_subscriptions_for_user`, `job_matching.push.send_push_notification`),
keeping the same call shape and behavior the plan describes.
"""

from __future__ import annotations

from app.auth.models import User
from app.modules.interview_scheduling.ics_builder import build_google_calendar_link
from app.modules.interview_scheduling.models import InterviewSchedule
from app.modules.interview_scheduling.schemas import InterviewScheduleResponse
from app.modules.job_matching import push
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.job_matching.repository import list_subscriptions_for_user
from app.services.email_service import EmailTemplate, get_email_service
from sqlalchemy.ext.asyncio import AsyncSession


def _to_response(schedule: InterviewSchedule) -> InterviewScheduleResponse:
    return InterviewScheduleResponse(
        id=str(schedule.id),
        job_match_id=str(schedule.job_match_id),
        scheduled_at=schedule.scheduled_at,
        duration_minutes=schedule.duration_minutes,
        notes=schedule.notes,
        ics_download_url=f"/api/interviews/matches/{schedule.job_match_id}/schedule.ics",
        google_calendar_link=build_google_calendar_link(
            summary="Interview",  # router builds the title/company-specific version for the .ics;
            description=schedule.notes
            or "",  # this response-level link is a generic fallback shown
            location=None,  # inline in the UI before a page navigation, refined client-side if needed
            start=schedule.scheduled_at,
            duration_minutes=schedule.duration_minutes,
        ),
        created_at=schedule.created_at,
    )


async def _send_scheduled_notification(
    db: AsyncSession,
    user: User,
    match: JobMatch,
    posting: JobPosting | None,
    schedule: InterviewSchedule,
) -> None:
    title = posting.title if posting else "your role"
    company = posting.company if posting else "the company"
    await get_email_service().send_template(
        EmailTemplate.INTERVIEW_SCHEDULED,
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
    subs = await list_subscriptions_for_user(db, user.id)
    for sub in subs:
        await push.send_push_notification(
            sub,
            {
                "event": "interview_scheduled",
                "title": title,
                "company": company,
                "scheduled_at": schedule.scheduled_at.isoformat(),
            },
        )
