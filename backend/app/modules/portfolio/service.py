"""Business logic for portfolio profiles, items, and Portfolio Studio revisions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.portfolio.content import (
    PortfolioContent,
    PortfolioProject,
    PortfolioRevision,
    empty_revision,
    hydrate_revision_from_legacy,
    revision_from_dict,
    revision_to_dict,
)
from app.modules.portfolio.models import PortfolioItem, PortfolioProfile
from app.modules.portfolio.repository import (
    get_profile_by_slug,
    get_profile_by_user_id,
    list_items_for_profile,
)
from app.modules.portfolio.schemas import (
    PortfolioItemRequest,
    PortfolioItemResponse,
    PortfolioItemType,
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
        items = await list_items_for_profile(self.db, profile.id) if profile else []

        if profile:
            draft = self._ensure_draft(profile, items)
            draft = self._apply_studio_updates(draft, body)
            # Keep legacy columns in sync for admin list views / BC clients.
            if body.content is not None:
                profile.display_name = body.content.display_name or body.display_name
                profile.headline = body.content.headline or body.headline
                profile.bio = body.content.summary or body.bio
            else:
                profile.display_name = body.display_name
                profile.headline = body.headline
                profile.bio = body.bio
                # Mirror legacy fields into draft content when studio content omitted.
                draft.content.display_name = body.display_name
                draft.content.headline = body.headline
                draft.content.summary = body.bio
                if body.bio and not draft.content.about:
                    draft.content.about = body.bio

            profile.slug = body.slug
            profile.draft_revision = revision_to_dict(draft)
            profile.updated_at = datetime.now(UTC)

            if body.publish:
                profile.published_revision = revision_to_dict(draft)
                profile.is_published = True
                self._sync_legacy_from_revision(profile, draft)
            else:
                # BC: is_published toggle without full republish still controls visibility.
                profile.is_published = body.is_published
                if body.is_published and profile.published_revision is None:
                    # First publish via legacy toggle — snapshot current draft.
                    profile.published_revision = revision_to_dict(draft)
        else:
            draft = self._apply_studio_updates(empty_revision(), body)
            if body.content is None:
                draft.content.display_name = body.display_name
                draft.content.headline = body.headline
                draft.content.summary = body.bio
                draft.content.about = body.bio
            profile = PortfolioProfile(
                id=uuid4(),
                user_id=user_id,
                slug=body.slug,
                display_name=draft.content.display_name or body.display_name,
                headline=draft.content.headline or body.headline,
                bio=draft.content.summary or body.bio,
                is_published=body.publish or body.is_published,
                draft_revision=revision_to_dict(draft),
                published_revision=(
                    revision_to_dict(draft) if (body.publish or body.is_published) else None
                ),
            )
            self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(profile)
        return await self._to_response(profile)

    async def publish_profile(self, user_id: UUID) -> PortfolioProfileResponse:
        """Copy draft → published and set is_published=True."""
        profile = await get_profile_by_user_id(self.db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No portfolio profile yet"
            )
        items = await list_items_for_profile(self.db, profile.id)
        draft = self._ensure_draft(profile, items)
        profile.published_revision = revision_to_dict(draft)
        profile.is_published = True
        self._sync_legacy_from_revision(profile, draft)
        profile.updated_at = datetime.now(UTC)
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
        # Mirror into draft revision projects for studio templates.
        items = await list_items_for_profile(self.db, profile.id)
        draft = self._ensure_draft(profile, items)
        draft.content.projects.append(
            PortfolioProject(
                id=str(item.id),
                title=body.title,
                description=body.description,
                image_url=body.image_url,
                demo_url=None if body.item_type == "github" else body.url,
                repo_url=body.url if body.item_type == "github" else None,
                display_order=body.display_order,
            )
        )
        profile.draft_revision = revision_to_dict(draft)
        profile.updated_at = datetime.now(UTC)
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
        draft = self._ensure_draft(profile, items)
        draft.content.projects = [p for p in draft.content.projects if p.id != item_id]
        profile.draft_revision = revision_to_dict(draft)
        profile.updated_at = datetime.now(UTC)
        await self.db.commit()

    async def get_public_profile(self, slug: str) -> PublicPortfolioResponse:
        """Unauthenticated lookup — published revision only (Decision 4 + Studio)."""
        profile = await get_profile_by_slug(self.db, slug)
        if not profile or not profile.is_published or profile.admin_hidden:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
        items = await list_items_for_profile(self.db, profile.id)
        published = self._resolve_published(profile, items)
        return PublicPortfolioResponse(
            slug=profile.slug,
            display_name=published.content.display_name or profile.display_name,
            headline=published.content.headline or profile.headline,
            bio=published.content.summary or profile.bio,
            items=[self._item_to_response(i) for i in items],
            template_id=published.template_id,
            theme=published.theme,
            content=published.content,
            section_visibility=published.section_visibility,
            section_order=published.section_order,
        )

    async def _to_response(self, profile: PortfolioProfile) -> PortfolioProfileResponse:
        items = await list_items_for_profile(self.db, profile.id)
        draft = self._ensure_draft(profile, items)
        published = (
            revision_from_dict(profile.published_revision) if profile.published_revision else None
        )
        base_url = self._settings.portfolio_public_base_url or "/p"
        return PortfolioProfileResponse(
            profile_id=str(profile.id),
            user_id=str(profile.user_id),
            slug=profile.slug,
            display_name=draft.content.display_name or profile.display_name,
            headline=draft.content.headline or profile.headline,
            bio=draft.content.summary or profile.bio,
            is_published=profile.is_published,
            public_url=f"{base_url}/{profile.slug}",
            items=[self._item_to_response(i) for i in items],
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            template_id=draft.template_id,
            theme=draft.theme,
            content=draft.content,
            section_visibility=draft.section_visibility,
            section_order=draft.section_order,
            has_unpublished_changes=self._has_unpublished_changes(draft, published),
            draft_revision=draft,
            published_revision=published,
        )

    def _item_to_response(self, item: PortfolioItem) -> PortfolioItemResponse:
        return PortfolioItemResponse(
            item_id=str(item.id),
            item_type=cast(PortfolioItemType, item.item_type),
            title=item.title,
            description=item.description,
            url=item.url,
            image_url=item.image_url,
            display_order=item.display_order,
            created_at=item.created_at,
        )

    def _ensure_draft(
        self, profile: PortfolioProfile, items: list[PortfolioItem]
    ) -> PortfolioRevision:
        raw = profile.draft_revision
        if raw:
            return revision_from_dict(raw)
        legacy_items = [
            {
                "id": str(i.id),
                "item_type": i.item_type,
                "title": i.title,
                "description": i.description,
                "url": i.url,
                "image_url": i.image_url,
                "display_order": i.display_order,
            }
            for i in items
        ]
        return hydrate_revision_from_legacy(
            display_name=profile.display_name,
            headline=profile.headline,
            bio=profile.bio,
            items=legacy_items,
        )

    def _resolve_published(
        self, profile: PortfolioProfile, items: list[PortfolioItem]
    ) -> PortfolioRevision:
        if profile.published_revision:
            return revision_from_dict(profile.published_revision)
        # Legacy published profiles without a snapshot — fall back to columns + items.
        return self._ensure_draft(profile, items)

    def _apply_studio_updates(
        self, draft: PortfolioRevision, body: PortfolioProfileRequest
    ) -> PortfolioRevision:
        data = revision_to_dict(draft)
        if body.template_id is not None:
            data["template_id"] = body.template_id
        if body.theme is not None:
            data["theme"] = body.theme.model_dump(mode="json")
        if body.content is not None:
            data["content"] = body.content.model_dump(mode="json")
        if body.section_visibility is not None:
            data["section_visibility"] = body.section_visibility
        if body.section_order is not None:
            data["section_order"] = body.section_order
        return revision_from_dict(data)

    def _sync_legacy_from_revision(
        self, profile: PortfolioProfile, revision: PortfolioRevision
    ) -> None:
        profile.display_name = revision.content.display_name
        profile.headline = revision.content.headline
        profile.bio = revision.content.summary

    @staticmethod
    def _has_unpublished_changes(
        draft: PortfolioRevision, published: PortfolioRevision | None
    ) -> bool:
        if published is None:
            return True
        return revision_to_dict(draft) != revision_to_dict(published)

    # Expose for tests / migration helpers
    @staticmethod
    def build_content(**kwargs: Any) -> PortfolioContent:
        return PortfolioContent(**kwargs)
