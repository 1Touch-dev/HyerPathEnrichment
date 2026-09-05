"""Data-access layer for outreach. Workers import this, never service.py."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.outreach.models import EmployerCompanyTier, OutreachMessage


async def get_owned_message(
    db: AsyncSession, message_id: UUID, user_id: UUID
) -> OutreachMessage | None:
    result = await db.execute(
        select(OutreachMessage).where(
            OutreachMessage.id == message_id, OutreachMessage.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def list_messages_for_user(
    db: AsyncSession, user_id: UUID, limit: int = 50
) -> list[OutreachMessage]:
    result = await db.execute(
        select(OutreachMessage)
        .where(OutreachMessage.user_id == user_id)
        .order_by(OutreachMessage.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_sent(db: AsyncSession, message: OutreachMessage) -> OutreachMessage:
    message.status = "sent"
    message.sent_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(message)
    return message


async def get_company_tier(db: AsyncSession, company_name: str) -> EmployerCompanyTier | None:
    result = await db.execute(
        select(EmployerCompanyTier).where(EmployerCompanyTier.company_name == company_name)
    )
    return result.scalar_one_or_none()


async def set_company_tier(
    db: AsyncSession,
    *,
    company_name: str,
    tier: str,
    set_by: Literal["llm", "recruiter"],
    set_by_user_id: UUID | None,
    notes: str | None,
    update_notes: bool = True,
) -> EmployerCompanyTier:
    """Upsert by ``company_name`` — a recruiter re-setting an existing employer's
    tier overwrites the previous value/set_by/set_by_user_id/updated_at rather
    than creating a duplicate row (enforced at the DB level too via the unique
    constraint on ``company_name``). This function always overwrites
    unconditionally regardless of the existing row's ``set_by`` — the
    override-preservation rule (a recruiter-set row must survive a later
    classifier run) is enforced one layer up, in the classifier's own
    write-path (see ``apply_classified_company_tier`` in ``service.py``), not
    here, since a recruiter's own explicit call to this function must still be
    able to overwrite anything, including their own prior value.

    ``update_notes`` defaults to ``True`` for backwards-compatible callers.
    When ``False``, the update branch below leaves ``existing.notes``
    untouched regardless of what was passed in ``notes`` — this is how the
    router's sentinel handling (see ``SetCompanyTierRequest`` in
    ``schemas.py``) implements "field omitted from the request body" without
    clobbering a previously-saved note. The insert branch always uses
    ``notes`` as given (a brand-new row has no existing note to preserve)."""
    existing = await get_company_tier(db, company_name)
    if existing is not None:
        existing.tier = tier
        existing.set_by = set_by
        existing.set_by_user_id = set_by_user_id
        if update_notes:
            existing.notes = notes
        existing.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(existing)
        return existing

    row = EmployerCompanyTier(
        company_name=company_name,
        tier=tier,
        set_by=set_by,
        set_by_user_id=set_by_user_id,
        notes=notes,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row
