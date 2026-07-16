"""Persisted change-signal storage."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SignalListItem, SignalRecord


async def create_signal(
    db: AsyncSession,
    *,
    watch_id: str,
    title: str,
    url: str,
    timestamp: str | None = None,
    source: str = "changedetection",
) -> SignalListItem:
    record = SignalRecord(
        id=f"sig_{uuid4().hex}",
        source=source,
        watch_id=watch_id,
        title=title,
        url=url,
        signal_timestamp=timestamp,
    )
    db.add(record)
    await db.flush()
    await db.commit()
    await db.refresh(record)
    return _to_list_item(record)


async def list_signals(
    db: AsyncSession,
    limit: int,
    offset: int,
) -> tuple[list[SignalListItem], int]:
    clamped_limit = max(1, min(limit, 100))
    clamped_offset = max(0, offset)

    total_result = await db.execute(select(func.count()).select_from(SignalRecord))
    total = int(total_result.scalar_one())

    statement = (
        select(SignalRecord)
        .order_by(SignalRecord.created_at.desc())
        .limit(clamped_limit)
        .offset(clamped_offset)
    )
    result = await db.execute(statement)
    records = list(result.scalars().all())
    return [_to_list_item(record) for record in records], total


def _to_list_item(record: SignalRecord) -> SignalListItem:
    return SignalListItem(
        id=record.id,
        source=record.source,
        watch_id=record.watch_id,
        title=record.title,
        url=record.url,
        timestamp=record.signal_timestamp,
        created_at=record.created_at,
    )
