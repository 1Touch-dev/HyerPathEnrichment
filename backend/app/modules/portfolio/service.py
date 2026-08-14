"""Business logic for portfolio profiles and items."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.portfolio.models import PortfolioItem, PortfolioProfile
from app.modules.portfolio.repository import (
    get_profile_by_slug,
    get_profile_by_user_id,
    list_items_for_profile,
)
from app.modules.portfolio.schemas import (
    PortfolioItemRequest,
    PortfolioItemResponse,
    PortfolioProfileRequest,
    PortfolioProfileResponse,
    PublicPortfolioResponse,
)


class PortfolioService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._settings = get_settings()

    async def upsert_profile(
        self, user_id: UUID, body: PortfolioProfileRequest
    ) -> PortfolioProfileResponse:
        existing_slug_owner = await get_profile_by_slug(self.db, body.slug)
        if existing_slug_owner and existing_slug_owner.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")

        profile = await get_profile_by_user_id(self.db, user_id)
        if profile:
            profile.slug = body.slug
            profile.display_name = body.display_name
            profile.headline = body.headline
            profile.bio = body.bio
            profile.is_published = body.is_published
            profile.updated_at = datetime.now(UTC)
        else:
            profile = PortfolioProfile(
                id=uuid4(),
                user_id=user_id,
                slug=body.slug,
                display_name=body.display_name,
                headline=body.headline,
                bio=body.bio,
                is_published=body.is_published,
            )
            self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return await self._to_response(profile)

    async def get_my_profile(self, user_id: UUID) -> PortfolioProfileResponse:
        profile = await get_profile_by_user_id(self.db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No portfolio profile yet"
            )
        return await self._to_response(profile)

    async def add_item(self, user_id: UUID, body: PortfolioItemRequest) -> PortfolioItemResponse:
        profile = await get_profile_by_user_id(self.db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Create a portfolio profile before adding items",
            )
        item = PortfolioItem(
            id=uuid4(),
            profile_id=profile.id,
            item_type=body.item_type,
            title=body.title,
            description=body.description,
            url=body.url,
            image_url=body.image_url,
            display_order=body.display_order,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return self._item_to_response(item)

    async def delete_item(self, user_id: UUID, item_id: str) -> None:
        profile = await get_profile_by_user_id(self.db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No portfolio profile"
            )
        items = await list_items_for_profile(self.db, profile.id)
        target = next((i for i in items if str(i.id) == item_id), None)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        await self.db.delete(target)
        await self.db.commit()

    async def get_public_profile(self, slug: str) -> PublicPortfolioResponse:
        """Unauthenticated lookup — used by the public /p/{slug} page (Decision 4)."""
        profile = await get_profile_by_slug(self.db, slug)
        if not profile or not profile.is_published:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
        items = await list_items_for_profile(self.db, profile.id)
        return PublicPortfolioResponse(
            slug=profile.slug,
            display_name=profile.display_name,
            headline=profile.headline,
            bio=profile.bio,
            items=[self._item_to_response(i) for i in items],
        )

    async def _to_response(self, profile: PortfolioProfile) -> PortfolioProfileResponse:
        items = await list_items_for_profile(self.db, profile.id)
        base_url = self._settings.portfolio_public_base_url or "/p"
        return PortfolioProfileResponse(
            profile_id=str(profile.id),
            user_id=str(profile.user_id),
            slug=profile.slug,
            display_name=profile.display_name,
            headline=profile.headline,
            bio=profile.bio,
            is_published=profile.is_published,
            public_url=f"{base_url}/{profile.slug}",
            items=[self._item_to_response(i) for i in items],
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def _item_to_response(self, item: PortfolioItem) -> PortfolioItemResponse:
        return PortfolioItemResponse(
            item_id=str(item.id),
            item_type=item.item_type,
            title=item.title,
            description=item.description,
            url=item.url,
            image_url=item.image_url,
            display_order=item.display_order,
            created_at=item.created_at,
        )
