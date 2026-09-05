"""Tests for the portfolio module: profile CRUD, slug validation, public lookup."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect

from alembic import command
from app.auth.models import User
from app.modules.portfolio.schemas import PortfolioItemRequest, PortfolioProfileRequest
from app.modules.portfolio.service import PortfolioService
from tests.migration_helpers import alembic_config, sqlite_file_url, sync_engine_for, upgrade_head


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

    req2 = PortfolioProfileRequest(
        slug="john-doe", headline="Senior Backend Engineer", is_published=True
    )
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
    await service.upsert_profile(
        test_user.id, PortfolioProfileRequest(slug="hidden-one", is_published=False)
    )
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
    await service.upsert_profile(
        test_user.id, PortfolioProfileRequest(slug="visible-one", is_published=True)
    )
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
            item_type="github",
            title="My Project",
            description="A thing",
            url="https://github.com/x/y",
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


async def test_add_item_with_image_url_round_trips_through_my_and_public_profile(db, test_user):
    """image_url is optional but, when set, must survive both the owner-facing
    get_my_profile response and the public get_public_profile response."""
    service = PortfolioService(db)
    await service.upsert_profile(
        test_user.id, PortfolioProfileRequest(slug="image-url-profile", is_published=True)
    )
    item = await service.add_item(
        test_user.id,
        PortfolioItemRequest(
            item_type="github",
            title="Project With Thumbnail",
            url="https://github.com/x/y",
            image_url="https://cdn.example.com/thumb.png",
        ),
    )
    assert item.image_url == "https://cdn.example.com/thumb.png"

    my_profile = await service.get_my_profile(test_user.id)
    assert my_profile.items[0].image_url == "https://cdn.example.com/thumb.png"

    public_profile = await service.get_public_profile("image-url-profile")
    assert public_profile.items[0].image_url == "https://cdn.example.com/thumb.png"


async def test_add_item_without_image_url_defaults_to_none(db, test_user):
    service = PortfolioService(db)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="no-image-url"))
    item = await service.add_item(
        test_user.id,
        PortfolioItemRequest(item_type="other", title="No Thumbnail", url="https://example.com"),
    )
    assert item.image_url is None

    my_profile = await service.get_my_profile(test_user.id)
    assert my_profile.items[0].image_url is None


@pytest.fixture
def migration_sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "portfolio_image_url_migrate.db")


def _portfolio_items_columns(url: str) -> dict[str, dict]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            return {c["name"]: c for c in inspect(conn).get_columns("portfolio_items")}
    finally:
        engine.dispose()


def test_migration_032_adds_image_url_and_reverses_cleanly(migration_sqlite_url: str):
    """Alembic revision 032_portfolio_item_image_url must apply cleanly on top of
    031_merge_jobcv_stab_heads, and downgrading back to 031 must
    drop image_url while leaving the rest of portfolio_items untouched.
    """
    upgrade_head(migration_sqlite_url)
    cols = _portfolio_items_columns(migration_sqlite_url)
    assert "image_url" in cols
    assert cols["image_url"]["nullable"] is True

    command.downgrade(alembic_config(migration_sqlite_url), "031_merge_jobcv_stab_heads")
    cols_after_downgrade = _portfolio_items_columns(migration_sqlite_url)
    assert "image_url" not in cols_after_downgrade
    assert {"id", "profile_id", "item_type", "title", "url", "display_order"} <= (
        cols_after_downgrade.keys()
    )

    upgrade_head(migration_sqlite_url)
    cols_after_reupgrade = _portfolio_items_columns(migration_sqlite_url)
    assert "image_url" in cols_after_reupgrade
