"""Data-access layer for outreach. Workers import this, never service.py."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.outreach.models import OutreachMessage


async def get_owned_message(db: AsyncSession, message_id: UUID, user_id: UUID) -> OutreachMessage | None:
    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.id == message_id, OutreachMessage.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_messages_for_user(db: AsyncSession, user_id: UUID, limit: int = 50) -> list[OutreachMessage]:
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
