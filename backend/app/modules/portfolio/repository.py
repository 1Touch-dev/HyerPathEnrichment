"""Data-access layer for portfolio. Workers (none exist for this module today) would import this, never service.py."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portfolio.models import PortfolioItem, PortfolioProfile


async def get_profile_by_user_id(db: AsyncSession, user_id: UUID) -> PortfolioProfile | None:
    result = await db.execute(select(PortfolioProfile).where(PortfolioProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def get_profile_by_slug(db: AsyncSession, slug: str) -> PortfolioProfile | None:
    result = await db.execute(select(PortfolioProfile).where(PortfolioProfile.slug == slug))
    return result.scalar_one_or_none()


async def list_items_for_profile(db: AsyncSession, profile_id: UUID) -> list[PortfolioItem]:
    result = await db.execute(
        select(PortfolioItem)
        .where(PortfolioItem.profile_id == profile_id)
        .order_by(PortfolioItem.display_order)
    )
    return list(result.scalars().all())
