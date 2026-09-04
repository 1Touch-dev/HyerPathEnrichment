"""Admin portfolio moderation: list/detail with filters, moderate happy path +
audit before/after, RBAC gate, and the critical interception test — an
admin-hidden profile must be indistinguishable from a nonexistent one via the
existing public GET /api/portfolio/public/{slug} route (phase2_admin_module.md
moderation layer, portfolio chunk)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.logging import scrub_sensitive_data
from app.modules.admin.models import AdminAuditLog
from app.modules.portfolio.models import PortfolioProfile
from app.modules.portfolio.schemas import PortfolioProfileRequest
from app.modules.portfolio.service import PortfolioService
from tests.envelope_helpers import assert_error, assert_success

pytestmark = pytest.mark.asyncio


def _idempotency_headers(auth_headers, user_id, key: str):
    return {**auth_headers(user_id), "Idempotency-Key": key}


def _ensure_portfolio_admin_router_mounted() -> None:
    """The admin portfolio router is intentionally NOT wired into
    app/modules/admin/__init__.py yet (held back for central wiring once all
    Batch-1 moderation chunks land — see task instructions). Mount it onto the
    real app singleton for this test module only, matching conftest.py's note
    that test files needing different behavior define their own local
    `client` fixture. Idempotent so re-running within the same session (or
    across test functions) never registers duplicate routes."""
    from app.main import app
    from app.modules.admin.portfolio_router import router as portfolio_admin_router

    prefix = "/api/admin/portfolio"
    already_mounted = any(getattr(r, "path", "").startswith(prefix) for r in app.routes)
    if not already_mounted:
        app.include_router(portfolio_admin_router)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    _ensure_portfolio_admin_router_mounted()
    return TestClient(app)


@pytest.fixture
async def profile_factory(db_session):
    async def _make(*, user=None, slug: str | None = None, **overrides) -> PortfolioProfile:
        from app.auth.models import User

        if user is None:
            user = User(
                id=uuid4(),
                email=f"portfolio-owner-{uuid4().hex[:8]}@example.com",
                first_name="Owner",
                last_name="User",
                is_active=True,
                is_verified=True,
            )
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)

        defaults = {
            "id": uuid4(),
            "user_id": user.id,
            "slug": slug or f"profile-{uuid4().hex[:10]}",
            "display_name": "Test Candidate",
            "headline": "Backend Engineer",
            "is_published": True,
            "admin_hidden": False,
        }
        defaults.update(overrides)
        profile = PortfolioProfile(**defaults)
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        return profile

    return _make


async def test_list_requires_permission(client):
    response = client.get("/api/admin/portfolio")
    assert response.status_code == 401


async def test_list_returns_cursor_shape(client, superuser, auth_headers, profile_factory):
    await profile_factory(slug="list-shape-one")
    response = client.get("/api/admin/portfolio", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body
    assert any(item["slug"] == "list-shape-one" for item in body["items"])


async def test_list_filters_by_is_published(client, superuser, auth_headers, profile_factory):
    await profile_factory(slug="filter-published", is_published=True)
    await profile_factory(slug="filter-unpublished", is_published=False)

    response = client.get(
        "/api/admin/portfolio",
        params={"is_published": "false"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    slugs = {item["slug"] for item in body["items"]}
    assert "filter-unpublished" in slugs
    assert "filter-published" not in slugs


async def test_list_filters_by_admin_hidden(client, superuser, auth_headers, profile_factory):
    await profile_factory(slug="filter-hidden", admin_hidden=True)
    await profile_factory(slug="filter-visible", admin_hidden=False)

    response = client.get(
        "/api/admin/portfolio",
        params={"admin_hidden": "true"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    slugs = {item["slug"] for item in body["items"]}
    assert "filter-hidden" in slugs
    assert "filter-visible" not in slugs


async def test_list_regular_user_forbidden(client, regular_user, auth_headers):
    response = client.get("/api/admin/portfolio", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_get_detail_includes_items(
    client, superuser, auth_headers, profile_factory, db_session
):
    from app.modules.portfolio.models import PortfolioItem

    profile = await profile_factory(slug="detail-with-items")
    item = PortfolioItem(
        id=uuid4(),
        profile_id=profile.id,
        item_type="github",
        title="A Project",
        url="https://github.com/x/y",
        display_order=0,
    )
    db_session.add(item)
    await db_session.commit()

    response = client.get(f"/api/admin/portfolio/{profile.id}", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert body["slug"] == "detail-with-items"
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "A Project"


async def test_get_detail_404_for_unknown_profile(client, superuser, auth_headers):
    response = client.get(f"/api/admin/portfolio/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


async def test_moderate_hides_profile_and_writes_audit(
    client, superuser, auth_headers, profile_factory, db_session
):
    profile = await profile_factory(slug="moderate-hide-me", admin_hidden=False)

    response = client.post(
        f"/api/admin/portfolio/{profile.id}/moderate",
        json={"admin_hidden": True, "reason": "Inappropriate content"},
        headers=_idempotency_headers(auth_headers, superuser.id, f"portfolio-hide-{profile.id}"),
    )
    body = assert_success(response)
    assert body["admin_hidden"] is True

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "portfolio.moderate",
            AdminAuditLog.target_id == str(profile.id),
        )
    )
    entry = result.scalar_one()
    assert entry.before == scrub_sensitive_data({"admin_hidden": False})
    assert entry.after == scrub_sensitive_data(
        {"admin_hidden": True, "reason": "Inappropriate content"}
    )


async def test_moderate_unhides_profile_toggles_both_ways(
    client, superuser, auth_headers, profile_factory, db_session
):
    profile = await profile_factory(slug="moderate-unhide-me", admin_hidden=True)

    response = client.post(
        f"/api/admin/portfolio/{profile.id}/moderate",
        json={"admin_hidden": False, "reason": "False positive"},
        headers=_idempotency_headers(auth_headers, superuser.id, f"portfolio-unhide-{profile.id}"),
    )
    body = assert_success(response)
    assert body["admin_hidden"] is False

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "portfolio.moderate",
            AdminAuditLog.target_id == str(profile.id),
        )
    )
    entry = result.scalar_one()
    assert entry.before == scrub_sensitive_data({"admin_hidden": True})
    assert entry.after == scrub_sensitive_data({"admin_hidden": False, "reason": "False positive"})


async def test_moderate_404_for_unknown_profile(client, superuser, auth_headers):
    response = client.post(
        f"/api/admin/portfolio/{uuid4()}/moderate",
        json={"admin_hidden": True, "reason": None},
        headers=_idempotency_headers(auth_headers, superuser.id, "portfolio-missing"),
    )
    assert_error(response, 404)


async def test_support_role_can_read_but_not_moderate(
    client, support_user, auth_headers, profile_factory
):
    profile = await profile_factory(slug="support-rbac-check")

    read_response = client.get("/api/admin/portfolio", headers=auth_headers(support_user.id))
    assert_success(read_response)

    moderate_response = client.post(
        f"/api/admin/portfolio/{profile.id}/moderate",
        json={"admin_hidden": True, "reason": "test"},
        headers=_idempotency_headers(auth_headers, support_user.id, "portfolio-support-forbidden"),
    )
    assert_error(moderate_response, 403)


async def test_moderate_requires_idempotency_key(client, superuser, auth_headers, profile_factory):
    profile = await profile_factory(slug="portfolio-missing-key")
    response = client.post(
        f"/api/admin/portfolio/{profile.id}/moderate",
        json={"admin_hidden": True, "reason": "Inappropriate content"},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 400)


async def test_admin_hidden_profile_indistinguishable_from_nonexistent_via_public_route(
    client, superuser, auth_headers, profile_factory, db
):
    """End-to-end: hide a published profile via the admin moderate endpoint,
    then verify the existing unauthenticated public route
    (GET /api/portfolio/public/{slug}) returns the exact same not-found
    response it would for a genuinely nonexistent slug — proving the
    interception happens in the real request path, not just in the DB."""
    profile = await profile_factory(slug="publicly-hidden", is_published=True)

    moderate_response = client.post(
        f"/api/admin/portfolio/{profile.id}/moderate",
        json={"admin_hidden": True, "reason": "policy violation"},
        headers=_idempotency_headers(auth_headers, superuser.id, "portfolio-publicly-hidden"),
    )
    assert_success(moderate_response)

    hidden_public_response = client.get("/api/portfolio/public/publicly-hidden")
    nonexistent_public_response = client.get("/api/portfolio/public/does-not-exist-at-all")

    assert hidden_public_response.status_code == nonexistent_public_response.status_code == 404
    hidden_body = assert_error(hidden_public_response, 404)
    nonexistent_body = assert_error(nonexistent_public_response, 404)
    assert hidden_body["error"]["message"] == nonexistent_body["error"]["message"]

    # Also verify directly through the service, matching this module's other
    # portfolio tests' conventions (tests/test_portfolio.py).
    from fastapi import HTTPException

    service = PortfolioService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_public_profile("publicly-hidden")
    assert exc_info.value.status_code == 404


async def test_moderating_unpublished_profile_still_returns_404_via_public_route(
    client, superuser, auth_headers, profile_factory
):
    """Sanity check: an admin_hidden=False, is_published=False profile is
    already 404 via the public route on its own (pre-existing behavior from
    tests/test_portfolio.py); this chunk's change must not alter that."""
    await profile_factory(slug="never-published", is_published=False, admin_hidden=False)
    response = client.get("/api/portfolio/public/never-published")
    assert_error(response, 404)


async def test_upsert_profile_request_schema_accepts_existing_fields():
    """Guard against accidental signature drift in PortfolioProfileRequest
    while this chunk edits the sibling models.py file."""
    req = PortfolioProfileRequest(slug="schema-guard", is_published=True)
    assert req.slug == "schema-guard"
