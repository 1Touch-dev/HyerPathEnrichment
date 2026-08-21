"""Generic moderation review-queue endpoints (Batch 1): list, detail, decide.

Owns AdminReviewQueueItem's router only — domain-specific moderation routers
(job_postings/documents/portfolio/outreach/job_swipe/questions/practice_audio)
are separate, concurrently-developed chunks and are NOT imported here.

Design note: the domain ORM model files (job_matching/documents/portfolio/
outreach models.py) are being edited concurrently in sibling worktrees and are
not safely importable from here. Resource resolution (GET detail) and the
domain-column flip on rejection (POST decide) are both implemented via raw
sa.table() constructs + AsyncSession execution — the same "table object,
not ORM model" pattern this repo's own migrations use (see
alembic/versions/038_admin_seed_roles_permissions.py) — which only requires
the DB columns to already exist (true as of migration 040), not any
particular ORM mapping.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_review_queue_decide_rate_limit
from app.modules.admin.audit import record_admin_action
from app.modules.admin.models import AdminReviewQueueItem
from app.modules.admin.pagination import decode_cursor, encode_cursor
from app.modules.admin.permissions import require_permission
from app.workers.queue import enqueue_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/review-queue", tags=["admin"], route_class=EnvelopeAPIRoute)

# resource_type -> (table_name, columns to select for the detail snapshot).
# "question"/"practice_audio" are Module-3 placeholders with no app-level
# table on this branch yet, so they are deliberately absent from this map.
_RESOURCE_TABLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "job_posting": ("job_postings", ("id", "title", "company", "moderation_status")),
    "document": ("candidate_documents", ("id", "user_id", "original_filename", "deleted_at")),
    "portfolio_item": ("portfolio_items", ("id", "profile_id", "title", "url")),
    "outreach_message": (
        "outreach_messages",
        ("id", "user_id", "company_name", "subject", "admin_blocked"),
    ),
}

# Module-3 placeholders per the plan: no app-level table/model exists for
# these on this branch yet, so both resolution and the decide-time domain
# flip are deliberate no-ops for them.
_MODULE_3_PLACEHOLDER_TYPES = frozenset({"question", "practice_audio"})

# Column names that hold UUID values in the raw sa.table() constructs below.
# These must use sa.Uuid() (not a bare sa.column()) so bound Python UUID
# values are adapted the same way SQLAlchemy's Mapped[UUID] ORM columns are
# (dialect-native UUID on Postgres, hex-without-dashes on SQLite) — matching
# how the domain ORM models (job_matching/documents/portfolio/outreach) will
# store these same columns once wired up.
_UUID_COLUMNS = frozenset(
    {"id", "resource_id", "user_id", "profile_id", "moderated_by", "reviewed_by"}
)


def _sa_column(name: str) -> sa.ColumnClause[Any]:
    return sa.column(name, sa.Uuid()) if name in _UUID_COLUMNS else sa.column(name)


def _sa_table(name: str, *columns: str) -> sa.TableClause:
    return sa.table(name, *(_sa_column(c) for c in columns))


class ReviewQueueItemResponse(BaseModel):
    id: UUID
    resource_type: str
    resource_id: UUID
    status: str
    flag_reason: str | None
    flag_source: str
    flagged_at: datetime
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None

    @classmethod
    def from_model(cls, item: AdminReviewQueueItem) -> ReviewQueueItemResponse:
        return cls(
            id=item.id,
            resource_type=item.resource_type,
            resource_id=item.resource_id,
            status=item.status,
            flag_reason=item.flag_reason,
            flag_source=item.flag_source,
            flagged_at=item.flagged_at,
            reviewed_by=item.reviewed_by,
            reviewed_at=item.reviewed_at,
            review_notes=item.review_notes,
        )


class ReviewQueueListResponse(BaseModel):
    items: list[ReviewQueueItemResponse]
    next_cursor: str | None
    has_more: bool


class ReviewQueueDetailResponse(BaseModel):
    item: ReviewQueueItemResponse
    resolved_resource: dict[str, Any] | None


class ReviewQueueDecideRequest(BaseModel):
    status: Literal["approved", "rejected"]
    review_notes: str | None = None


async def _resolve_resource(
    db: AsyncSession, resource_type: str, resource_id: UUID
) -> dict[str, Any] | None:
    """Best-effort snapshot of the underlying flagged resource. Returns None
    if the resource_type is a Module-3 placeholder, unrecognized, or the row
    is missing (never raises for those cases)."""
    if resource_type in _MODULE_3_PLACEHOLDER_TYPES:
        return None
    table_info = _RESOURCE_TABLES.get(resource_type)
    if table_info is None:
        return None

    table_name, columns = table_info
    table = _sa_table(table_name, *columns)
    result = await db.execute(sa.select(table).where(table.c.id == resource_id))
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _flip_domain_column(
    db: AsyncSession, resource_type: str, resource_id: UUID, actor_id: UUID, now: datetime
) -> None:
    """Flip the corresponding domain's moderation column on rejection. Raw
    sa.table() update — see module docstring for why this can't import the
    domain ORM models."""
    if resource_type == "job_posting":
        table = _sa_table("job_postings", "id", "moderation_status", "moderated_by", "moderated_at")
        await db.execute(
            table.update()
            .where(table.c.id == resource_id)
            .values(moderation_status="removed", moderated_by=actor_id, moderated_at=now)
        )
    elif resource_type == "document":
        table = _sa_table("candidate_documents", "id", "deleted_at")
        await db.execute(table.update().where(table.c.id == resource_id).values(deleted_at=now))
    elif resource_type == "portfolio_item":
        items_table = _sa_table("portfolio_items", "id", "profile_id")
        result = await db.execute(
            select(items_table.c.profile_id).where(items_table.c.id == resource_id)
        )
        profile_id = result.scalar_one_or_none()
        if profile_id is None:
            logger.warning(
                "review_queue.decide: portfolio_item %s has no matching profile_id; "
                "skipping admin_hidden flip",
                resource_id,
            )
        else:
            profiles_table = _sa_table("portfolio_profiles", "id", "admin_hidden")
            await db.execute(
                profiles_table.update()
                .where(profiles_table.c.id == profile_id)
                .values(admin_hidden=True)
            )
    elif resource_type == "outreach_message":
        table = _sa_table("outreach_messages", "id", "admin_blocked")
        await db.execute(table.update().where(table.c.id == resource_id).values(admin_blocked=True))
    elif resource_type in _MODULE_3_PLACEHOLDER_TYPES:
        logger.warning(
            "review_queue.decide: resource_type=%s is a Module-3 placeholder with no "
            "app-level table yet; no domain column flip performed",
            resource_type,
        )
    else:
        logger.warning(
            "review_queue.decide: unrecognized resource_type=%s; no domain column flip performed",
            resource_type,
        )


async def _lookup_notify_email(
    db: AsyncSession, resource_type: str, resource_id: UUID
) -> str | None:
    """Best-effort lookup of the affected user's email for a rejection
    notification. job_posting (scraped platform content, no owning candidate)
    and the Module-3 placeholders are skipped entirely."""
    user_id: UUID | None = None

    if resource_type == "document":
        table = _sa_table("candidate_documents", "id", "user_id")
        result = await db.execute(select(table.c.user_id).where(table.c.id == resource_id))
        user_id = result.scalar_one_or_none()
    elif resource_type == "portfolio_item":
        items_table = _sa_table("portfolio_items", "id", "profile_id")
        result = await db.execute(
            select(items_table.c.profile_id).where(items_table.c.id == resource_id)
        )
        profile_id = result.scalar_one_or_none()
        if profile_id is not None:
            profiles_table = _sa_table("portfolio_profiles", "id", "user_id")
            result = await db.execute(
                select(profiles_table.c.user_id).where(profiles_table.c.id == profile_id)
            )
            user_id = result.scalar_one_or_none()
    elif resource_type == "outreach_message":
        table = _sa_table("outreach_messages", "id", "user_id")
        result = await db.execute(select(table.c.user_id).where(table.c.id == resource_id))
        user_id = result.scalar_one_or_none()
    # job_posting and Module-3 placeholders: no owning candidate, skip lookup entirely.

    if user_id is None:
        return None

    users_table = _sa_table("users", "id", "email")
    result = await db.execute(select(users_table.c.email).where(users_table.c.id == user_id))
    return result.scalar_one_or_none()


@router.get("", response_model=ReviewQueueListResponse)
async def list_review_queue(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    resource_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    _user: User = Depends(require_permission("content_review", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> ReviewQueueListResponse:
    query = select(AdminReviewQueueItem).order_by(
        AdminReviewQueueItem.flagged_at.desc(), AdminReviewQueueItem.id.desc()
    )
    if resource_type is not None:
        query = query.where(AdminReviewQueueItem.resource_type == resource_type)
    if status_filter is not None:
        query = query.where(AdminReviewQueueItem.status == status_filter)
    if cursor:
        flagged_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (AdminReviewQueueItem.flagged_at < flagged_at)
            | (
                (AdminReviewQueueItem.flagged_at == flagged_at)
                & (AdminReviewQueueItem.id < UUID(entity_id))
            )
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].flagged_at, rows[-1].id) if has_more and rows else None

    return ReviewQueueListResponse(
        items=[ReviewQueueItemResponse.from_model(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{item_id}", response_model=ReviewQueueDetailResponse)
async def get_review_queue_item(
    item_id: UUID,
    _user: User = Depends(require_permission("content_review", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> ReviewQueueDetailResponse:
    item = await db.get(AdminReviewQueueItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review queue item not found")

    resolved = await _resolve_resource(db, item.resource_type, item.resource_id)
    return ReviewQueueDetailResponse(
        item=ReviewQueueItemResponse.from_model(item),
        resolved_resource=resolved,
    )


@router.post(
    "/{item_id}/decide",
    response_model=ReviewQueueItemResponse,
    dependencies=[Depends(enforce_admin_review_queue_decide_rate_limit)],
)
async def decide_review_queue_item(
    item_id: UUID,
    payload: ReviewQueueDecideRequest,
    request: Request,
    current_user: User = Depends(require_permission("content_review", "decide")),
    db: AsyncSession = Depends(get_db_session),
) -> ReviewQueueItemResponse:
    item = await db.get(AdminReviewQueueItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review queue item not found")

    before = {"status": item.status}
    now = datetime.now(UTC)

    item.reviewed_by = current_user.id
    item.reviewed_at = now
    item.status = payload.status
    item.review_notes = payload.review_notes

    if payload.status == "rejected":
        await _flip_domain_column(db, item.resource_type, item.resource_id, current_user.id, now)

    await db.flush()

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="review_queue.decide",
        target_type="review_queue_item",
        target_id=str(item_id),
        before=before,
        after={"status": payload.status, "review_notes": payload.review_notes},
        ip_address=get_client_ip(request),
    )
    await db.commit()
    await db.refresh(item)

    if payload.status == "rejected":
        try:
            email = await _lookup_notify_email(db, item.resource_type, item.resource_id)
            if email:
                enqueue_email(
                    "moderation_decision",
                    email,
                    {"resource_type": item.resource_type, "reason": payload.review_notes},
                )
        except Exception:
            logger.warning(
                "review_queue.decide: notification failed for item_id=%s resource_type=%s",
                item_id,
                item.resource_type,
                exc_info=True,
            )

    return ReviewQueueItemResponse.from_model(item)
