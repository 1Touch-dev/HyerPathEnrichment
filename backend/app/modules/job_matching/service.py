"""Business logic for job matching: preferences, match listing, feedback."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.modules.application_tracker import repository as application_tracker_repository
from app.modules.job_matching import repository
from app.modules.job_matching.models import JobMatch
from app.modules.job_matching.schemas import (
    JobMatchListResponse,
    JobMatchResponse,
    JobPreferencesRequest,
    JobPreferencesResponse,
    ScanTriggerResponse,
)
from app.observability.job_matching_metrics import job_matching_apply_clicks_total
from app.workers.queue import QUEUE_JOB_MATCHING, get_redis_connection


def _validate_redirect_scheme(url: str) -> None:
    """Security edge case: source_url is scraped from third-party job boards
    (JobSpy/JSearch) — this codebase does not control or sanitize that upstream
    data. A malformed or malicious scrape (e.g. `javascript:...`, `data:...`, or
    a bare relative path) must never reach RedirectResponse, since a browser
    following a non-http(s) "redirect" from an authenticated same-origin request
    is a real, if narrow, injection surface. Only `http`/`https` schemes are
    allowed through; anything else 404s exactly like a missing source_url would,
    so a malformed row fails closed rather than exposing scheme-specific behavior
    to a client probing for it.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise NotFoundError("This posting has no external application link")


class JobMatchingService:
    def __init__(self, db: AsyncSession, redis_conn: Redis | None = None):
        self.db = db
        self.redis_conn = redis_conn or get_redis_connection()

    async def get_preferences(self, user_id: UUID) -> JobPreferencesResponse:
        prefs = await repository.get_preferences(self.db, user_id)
        if not prefs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preferences not set")
        return JobPreferencesResponse(
            user_id=str(prefs.user_id),
            source_document_id=str(prefs.source_document_id) if prefs.source_document_id else None,
            desired_roles=prefs.desired_roles,
            desired_locations=prefs.desired_locations,
            remote_preference=cast(
                'Literal["remote", "hybrid", "onsite"] | None', prefs.remote_preference
            ),
            salary_min=prefs.salary_min,
            salary_max=prefs.salary_max,
            salary_currency=prefs.salary_currency,
            notification_channels=cast(
                'list[Literal["email", "sms", "webhook", "push"]]', prefs.notification_channels
            ),
            webhook_url=prefs.webhook_url,
            digest_frequency=cast('Literal["daily", "weekly", "off"]', prefs.digest_frequency),
            is_scan_enabled=prefs.is_scan_enabled,
            last_scanned_at=prefs.last_scanned_at,
            created_at=prefs.created_at,
            updated_at=prefs.updated_at,
        )

    async def upsert_preferences(
        self, user_id: UUID, payload: JobPreferencesRequest
    ) -> JobPreferencesResponse:
        # exclude_unset: only fields the client actually sent should overwrite existing
        # preferences. A full model_dump() would reset every omitted field back to its
        # schema default on every PUT, silently destroying previously-saved preferences.
        await repository.upsert_preferences(
            self.db, user_id, payload.model_dump(exclude_unset=True)
        )
        return await self.get_preferences(user_id)

    async def list_matches(self, user_id: UUID, limit: int, offset: int) -> JobMatchListResponse:
        rows, total = await repository.list_matches_for_user(self.db, user_id, limit, offset)
        matches = [
            JobMatchResponse(
                match_id=str(match.id),
                job_posting_id=str(posting.id),
                title=posting.title,
                company=posting.company,
                location=posting.location,
                remote=posting.remote,
                source=posting.source,
                source_url=posting.source_url,
                salary_min=posting.salary_min,
                salary_max=posting.salary_max,
                salary_currency=posting.salary_currency,
                overall_score=match.overall_score,
                score_breakdown=match.score_breakdown,
                explanation=match.explanation,
                is_new=match.notified_at is None,
                viewed_at=match.viewed_at,
                feedback=cast('Literal["up", "down"] | None', match.feedback),
                apply_clicked_at=match.apply_clicked_at,
                applied_at=match.applied_at,
                created_at=match.created_at,
            )
            for match, posting in rows
        ]
        return JobMatchListResponse(matches=matches, total=total, limit=limit, offset=offset)

    async def mark_viewed(self, match_id: str, user_id: UUID) -> None:
        found = await repository.mark_viewed(self.db, UUID(match_id), user_id)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    async def set_feedback(self, match_id: str, user_id: UUID, feedback: str) -> None:
        found = await repository.set_feedback(self.db, UUID(match_id), user_id, feedback)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    async def record_apply_click_and_get_redirect_url(self, match_id: str, user_id: UUID) -> str:
        owned = await repository.get_owned_match(self.db, UUID(match_id), user_id)
        if owned is None:
            raise NotFoundError("Match not found")
        match, posting = owned
        if posting is None or not posting.source_url:
            raise NotFoundError("This posting has no external application link")
        _validate_redirect_scheme(posting.source_url)
        await repository.record_apply_click(self.db, match.id)
        job_matching_apply_clicks_total.inc()
        return posting.source_url

    async def set_applied(self, match_id: str, user_id: UUID, applied: bool) -> None:
        found = await repository.set_applied(self.db, UUID(match_id), user_id, applied)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        if applied:
            owned = await repository.get_owned_match(self.db, UUID(match_id), user_id)
            if owned is not None and owned[0].application_status == "new":
                await application_tracker_repository.update_status(
                    self.db, UUID(match_id), user_id, "applied"
                )

    async def trigger_scan(self, user_id: UUID) -> ScanTriggerResponse:
        """Manual on-demand scan trigger (in addition to the daily cron, §7.7)."""
        try:
            queue = Queue(QUEUE_JOB_MATCHING, connection=self.redis_conn)
            queue.enqueue(
                "app.workers.tasks.job_matching.scan_jobs_for_candidate",
                str(user_id),
                job_timeout=120,
            )
            return ScanTriggerResponse(message="Scan enqueued", scan_enqueued=True)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enqueue scan: {exc}",
            )


_STATUS_ORDER: dict[str, int] = {
    "new": 0,
    "applied": 1,
    "replied": 2,
    "interview": 3,
    "offer": 4,
    "rejected": 4,
}


async def advance_application_status_if_earlier(
    db: AsyncSession, match: JobMatch, *, target: str
) -> None:
    """Forward-fill-only status advance, shared by Module B (mark-applied) and
    Module D (schedule-interview) — the "never downgrade a further-along status"
    rule lives in exactly one place instead of being reimplemented per module.
    """
    if _STATUS_ORDER[target] > _STATUS_ORDER[match.application_status]:
        match.application_status = target
        match.status_updated_at = datetime.now(UTC)
        await db.flush()
        await db.commit()
