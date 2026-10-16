"""Portfolio Studio: draft/publish isolation, template switching, content preservation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth.models import User
from app.modules.portfolio.content import PortfolioContent, PortfolioProject
from app.modules.portfolio.schemas import PortfolioProfileRequest
from app.modules.portfolio.service import PortfolioService


@pytest.fixture
async def test_user(db):
    user = User(
        id=uuid4(),
        email=f"studio-{uuid4().hex[:8]}@example.com",
        first_name="Studio",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_save_draft_does_not_expose_unpublished_content_publicly(db, test_user):
    service = PortfolioService(db)
    content = PortfolioContent(
        display_name="Ada",
        headline="Draft headline",
        summary="Secret draft",
        projects=[
            PortfolioProject(title="Secret project", demo_url="https://example.com/secret"),
        ],
    )
    await service.upsert_profile(
        test_user.id,
        PortfolioProfileRequest(
            slug="ada-draft",
            content=content,
            template_id="developer_dark",
            is_published=False,
            publish=False,
        ),
    )
    with pytest.raises(HTTPException) as exc:
        await service.get_public_profile("ada-draft")
    assert exc.value.status_code == 404


async def test_publish_copies_draft_and_public_sees_published_revision(db, test_user):
    service = PortfolioService(db)
    draft = PortfolioContent(display_name="Ada", headline="V1", summary="First")
    await service.upsert_profile(
        test_user.id,
        PortfolioProfileRequest(slug="ada-pub", content=draft, publish=True),
    )
    public = await service.get_public_profile("ada-pub")
    assert public.headline == "V1"
    assert public.content.headline == "V1"

    # Update draft without publishing
    await service.upsert_profile(
        test_user.id,
        PortfolioProfileRequest(
            slug="ada-pub",
            content=PortfolioContent(display_name="Ada", headline="V2 DRAFT", summary="Second"),
            template_id="creative_showcase",
            is_published=True,
            publish=False,
        ),
    )
    public_after = await service.get_public_profile("ada-pub")
    assert public_after.headline == "V1"
    assert public_after.template_id == "minimal_professional"

    mine = await service.get_my_profile(test_user.id)
    assert mine.content.headline == "V2 DRAFT"
    assert mine.template_id == "creative_showcase"
    assert mine.has_unpublished_changes is True

    published = await service.publish_profile(test_user.id)
    assert published.content.headline == "V2 DRAFT"
    public_live = await service.get_public_profile("ada-pub")
    assert public_live.headline == "V2 DRAFT"
    assert public_live.template_id == "creative_showcase"


async def test_template_switch_preserves_content(db, test_user):
    service = PortfolioService(db)
    content = PortfolioContent(
        display_name="Sam",
        headline="Builder",
        projects=[PortfolioProject(title="Alpha", tech_stack=["Go"])],
    )
    await service.upsert_profile(
        test_user.id,
        PortfolioProfileRequest(
            slug="sam-tpl", content=content, template_id="minimal_professional"
        ),
    )
    updated = await service.upsert_profile(
        test_user.id,
        PortfolioProfileRequest(
            slug="sam-tpl",
            content=content,
            template_id="executive_elegant",
        ),
    )
    assert updated.template_id == "executive_elegant"
    assert updated.content.projects[0].title == "Alpha"
    assert updated.content.projects[0].tech_stack == ["Go"]


async def test_accounts_remain_isolated(db, test_user):
    other = User(
        id=uuid4(),
        email=f"other-{uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(other)
    await db.commit()

    service = PortfolioService(db)
    await service.upsert_profile(
        test_user.id,
        PortfolioProfileRequest(
            slug="owner-a",
            content=PortfolioContent(headline="A"),
            publish=True,
        ),
    )
    await service.upsert_profile(
        other.id,
        PortfolioProfileRequest(
            slug="owner-b",
            content=PortfolioContent(headline="B"),
            publish=True,
        ),
    )
    a = await service.get_public_profile("owner-a")
    b = await service.get_public_profile("owner-b")
    assert a.headline == "A"
    assert b.headline == "B"
