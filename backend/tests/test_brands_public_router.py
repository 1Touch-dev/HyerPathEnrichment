"""Tests for the unauthenticated brand landing-page lookup endpoint
(GET /api/brands/public/{slug}) — see app/modules/brands/public_router.py and
public_schemas.py. Mirrors tests/test_portfolio.py and
tests/test_admin_portfolio_moderation.py's conventions for the sibling public
portfolio route: `db` fixture for direct row setup, `client` fixture (a plain
TestClient(app), no auth headers) for HTTP-level assertions, and
tests/envelope_helpers.py's assert_success/assert_error for the shared
response envelope.

The release-blocking tests here guard the one thing this endpoint must never
do: leak custom_domain, chatbot_config, or the internal id to an anonymous
landing-page visitor (docs/adr/0019-tenancy-model.md)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.brands.models import Brand
from app.modules.brands.public_schemas import PublicBrandResponse
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
async def brand_factory(db):
    async def _make(**overrides):
        fields = {
            "name": "Acme Recruiting",
            "slug": f"acme-{uuid4().hex[:8]}",
            "custom_domain": "careers.acme.example.com",
            "chatbot_config": {"tone": "friendly", "system_prompt": "You are Acme's assistant."},
            "landing_page_tier_config": {"tiers": ["free", "pro"], "headline": "Join Acme"},
            "is_active": True,
        }
        fields.update(overrides)
        brand = Brand(**fields)
        db.add(brand)
        await db.commit()
        await db.refresh(brand)
        return brand

    return _make


def test_public_brand_response_schema_has_exactly_three_fields():
    """Belt-and-suspenders against a future accidental field addition to
    PublicBrandResponse: only name, slug, landing_page_tier_config may ever
    be declared on this schema."""
    assert set(PublicBrandResponse.model_fields.keys()) == {
        "name",
        "slug",
        "landing_page_tier_config",
    }


async def test_public_brand_leaks_no_sensitive_fields(client, brand_factory):
    """RELEASE-BLOCKING: an active brand with every sensitive field populated
    (custom_domain, chatbot_config) must never surface those fields — or the
    internal id — anywhere in the response body, no matter where in the JSON
    tree they might appear."""
    brand = await brand_factory(
        slug="leak-test-brand",
        custom_domain="careers.leaktest.example.com",
        chatbot_config={"tone": "formal", "greeting": "Welcome to Leak Test Co"},
    )

    response = client.get("/api/brands/public/leak-test-brand")
    body = assert_success(response)

    assert set(body.keys()) == {"name", "slug", "landing_page_tier_config"}

    raw_text = response.text
    assert "custom_domain" not in raw_text
    assert "chatbot_config" not in raw_text
    assert '"id"' not in raw_text
    assert str(brand.id) not in raw_text


async def test_public_brand_returns_200_with_correct_fields(client, brand_factory):
    brand = await brand_factory(
        name="Acme Recruiting",
        slug="acme-recruiting-live",
        landing_page_tier_config={"tiers": ["free", "pro"], "headline": "Join Acme"},
        is_active=True,
    )

    response = client.get(f"/api/brands/public/{brand.slug}")
    body = assert_success(response)

    assert body["name"] == "Acme Recruiting"
    assert body["slug"] == "acme-recruiting-live"
    assert body["landing_page_tier_config"] == {"tiers": ["free", "pro"], "headline": "Join Acme"}


async def test_public_brand_404_for_nonexistent_slug(client):
    """RELEASE-BLOCKING."""
    response = client.get("/api/brands/public/does-not-exist-at-all")
    assert_error(response, 404)


async def test_public_brand_404_for_inactive_brand(client, brand_factory):
    """RELEASE-BLOCKING: an existing but is_active=False brand must 404 —
    never 200 with is_active info, and never a 500."""
    await brand_factory(slug="inactive-brand", is_active=False)

    response = client.get("/api/brands/public/inactive-brand")
    assert_error(response, 404)


async def test_public_brand_requires_no_authentication(client, brand_factory):
    """Confirm the endpoint works with literally no Authorization header —
    not merely that it also works when authenticated."""
    await brand_factory(slug="no-auth-needed")

    assert "authorization" not in {h.lower() for h in client.headers}
    response = client.get("/api/brands/public/no-auth-needed", headers={})

    body = assert_success(response)
    assert body["slug"] == "no-auth-needed"
