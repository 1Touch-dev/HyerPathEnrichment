"""Tests for the portfolio module: profile CRUD, slug validation, public lookup."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth.models import User
from app.modules.portfolio.schemas import PortfolioItemRequest, PortfolioProfileRequest
from app.modules.portfolio.service import PortfolioService


@pytest.fixture
async def test_user(db):
    user = User(
        id=uuid4(),
        email=f"portfolio-{uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def other_user(db):
    user = User(
        id=uuid4(),
        email=f"portfolio-other-{uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def test_slug_validation_rejects_leading_hyphen():
    with pytest.raises(ValidationError):
        PortfolioProfileRequest(slug="-johndoe")


def test_slug_validation_rejects_trailing_hyphen():
    with pytest.raises(ValidationError):
        PortfolioProfileRequest(slug="johndoe-")


def test_slug_validation_rejects_too_short():
    with pytest.raises(ValidationError):
        PortfolioProfileRequest(slug="jd")


def test_slug_validation_rejects_invalid_characters():
    with pytest.raises(ValidationError):
        PortfolioProfileRequest(slug="john_doe!")


def test_slug_validation_accepts_valid_slug():
    req = PortfolioProfileRequest(slug="john-doe-42")
    assert req.slug == "john-doe-42"


def test_slug_validation_normalizes_uppercase_to_lowercase():
    """Uppercase input is normalized (lowercased), not rejected — Decision 4."""
    req = PortfolioProfileRequest(slug="JohnDoe")
    assert req.slug == "johndoe"


async def test_upsert_profile_creates_then_updates(db, test_user):
    service = PortfolioService(db)
    req = PortfolioProfileRequest(slug="john-doe", headline="Backend Engineer", is_published=True)
    created = await service.upsert_profile(test_user.id, req)
    assert created.slug == "john-doe"

    req2 = PortfolioProfileRequest(slug="john-doe", headline="Senior Backend Engineer", is_published=True)
    updated = await service.upsert_profile(test_user.id, req2)
    assert updated.profile_id == created.profile_id
    assert updated.headline == "Senior Backend Engineer"


async def test_upsert_profile_rejects_slug_taken_by_another_user(db, test_user, other_user):
    service = PortfolioService(db)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="taken-slug"))
    with pytest.raises(HTTPException) as exc_info:
        await service.upsert_profile(other_user.id, PortfolioProfileRequest(slug="taken-slug"))
    assert exc_info.value.status_code == 409


async def test_upsert_profile_allows_same_owner_to_reuse_own_slug(db, test_user):
    service = PortfolioService(db)
    first = await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="my-own-slug"))
    second = await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="my-own-slug"))
    assert first.profile_id == second.profile_id


async def test_get_public_profile_hides_unpublished(db, test_user):
    service = PortfolioService(db)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="hidden-one", is_published=False))
    with pytest.raises(HTTPException) as exc_info:
        await service.get_public_profile("hidden-one")
    assert exc_info.value.status_code == 404


async def test_get_public_profile_404_for_unknown_slug(db):
    service = PortfolioService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_public_profile("does-not-exist")
    assert exc_info.value.status_code == 404


async def test_get_public_profile_returns_published(db, test_user):
    service = PortfolioService(db)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="visible-one", is_published=True))
    public = await service.get_public_profile("visible-one")
    assert public.slug == "visible-one"
    # Public response must never leak user_id (privacy — verified by schema shape, not just by value)
    assert not hasattr(public, "user_id")


async def test_my_profile_response_includes_user_id_and_public_url(db, test_user):
    service = PortfolioService(db)
    created = await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="owner-view"))
    assert created.user_id == str(test_user.id)
    assert created.public_url.endswith("/owner-view")


async def test_get_my_profile_404_when_none_created(db, test_user):
    service = PortfolioService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_my_profile(test_user.id)
    assert exc_info.value.status_code == 404


async def test_get_my_profile_returns_existing_profile(db, test_user):
    service = PortfolioService(db)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="my-visible-profile"))
    profile = await service.get_my_profile(test_user.id)
    assert profile.slug == "my-visible-profile"


async def test_add_item_requires_existing_profile(db, test_user):
    service = PortfolioService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.add_item(
            test_user.id,
            PortfolioItemRequest(item_type="github", title="Project", url="https://github.com/x/y"),
        )
    assert exc_info.value.status_code == 409


async def test_add_item_creates_item_for_existing_profile(db, test_user):
    service = PortfolioService(db)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="has-items"))
    item = await service.add_item(
        test_user.id,
        PortfolioItemRequest(
            item_type="github", title="My Project", description="A thing", url="https://github.com/x/y"
        ),
    )
    assert item.title == "My Project"
    assert item.item_type == "github"

    profile = await service.get_my_profile(test_user.id)
    assert len(profile.items) == 1
    assert profile.items[0].item_id == item.item_id


async def test_delete_item_404_when_no_profile(db, test_user):
    service = PortfolioService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_item(test_user.id, str(uuid4()))
    assert exc_info.value.status_code == 404


async def test_delete_item_404_for_unknown_item_id(db, test_user):
    service = PortfolioService(db)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="no-items-yet"))
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_item(test_user.id, str(uuid4()))
    assert exc_info.value.status_code == 404


async def test_delete_item_removes_item(db, test_user):
    service = PortfolioService(db)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="deletable-items"))
    item = await service.add_item(
        test_user.id,
        PortfolioItemRequest(item_type="live_demo", title="Demo", url="https://example.com"),
    )
    await service.delete_item(test_user.id, item.item_id)

    profile = await service.get_my_profile(test_user.id)
    assert profile.items == []
