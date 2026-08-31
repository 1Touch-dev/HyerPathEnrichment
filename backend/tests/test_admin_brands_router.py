"""Admin CRUD for Brand: `GET/POST /api/admin/brands`, `GET/PATCH
/api/admin/brands/{id}` (app/modules/brands/router.py), gated by
`require_permission("brands", "read"/"write")` (app/modules/admin/permissions.py)
and backed by `repository.list_all_brands`/`get_brand_by_id`/`create_brand`/
`update_brand` (app/modules/brands/repository.py). The ("brands", "read")/
("brands", "write") permissions themselves are seeded by
alembic/versions/056_seed_brands_permissions.py.

STRUCTURAL CHECK (not expressible as a pytest assertion): I read the full diff
of app/modules/brands/router.py and app/modules/brands/repository.py end to
end. Neither file contains a query that filters candidates, documents,
job_matches, job_postings, or any other table by `brand_id` -- every query in
both files operates only on the `brands` table itself (and, in repository.py,
the unrelated `recruiter_candidate_assignments` table, which is keyed by
recruiter/candidate user id, never brand_id). This matches
docs/adr/0019-tenancy-model.md's Decision that Brand is presentation-only and
is never used as an access-control/data-isolation scope.

Permission-gating "has the permission" cases use the `superuser` fixture
(is_superuser bypasses require_permission()'s DB lookup entirely -- see
app/modules/admin/permissions.py's `user_has_permission`), matching the
existing convention in test_admin_roles_crud.py's
`test_create_role_router_succeeds_for_superuser`. "Lacks the permission" cases
use `regular_user` (no role at all), which also never touches the buggy
role-permission join (see conftest.py's `SQLITE_ROLE_UUID_DASH_BUG_REASON`:
`user.role_id is None` short-circuits `user_has_permission` to `False` before
any query runs). One additional test below exercises the real, non-superuser
RolePermission grant path end to end for `brands:read`.

RELEASE-BLOCKING BUG FOUND WHILE WRITING THESE TESTS (now fixed):
`app/modules/brands/repository.py`'s `create_brand`/`update_brand` only called
`await db.flush()`, never `await db.commit()` -- unlike every other write
path in this codebase (e.g. `app/modules/admin/repository.py`'s
`create_role`/`attach_permission`, `app/modules/brands/deactivation_service.py`,
`app/modules/brands/assignment_service.py`, all of which call `db.commit()`
explicitly), and `app/database/session.py`'s `get_db_session()` never commits
on the caller's behalf either. `app/modules/brands/router.py` now calls
`await db.commit()` after `create_brand`/`update_brand` (matching the
router-owns-the-commit shape, since this module has no separate service.py
layer the way assignment/deactivation do). Both previously-failing tests
below now pass with the fix in place.

NOTE: this file does not follow the whole-module
`pytestmark = pytest.mark.asyncio` convention some other admin test files use,
because it mixes one sync test (the schema-level `is_active` guard) with
async ones -- same reasoning as test_admin_rbac.py's module docstring.
`pyproject.toml`'s `asyncio_mode = "auto"` already picks up the `async def`
tests without a marker.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.auth.models import User
from app.modules.brands.models import Brand
from tests.conftest import SQLITE_ROLE_UUID_DASH_BUG_REASON, USING_POSTGRES
from tests.envelope_helpers import assert_error, assert_success

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` here -- see the
# module docstring above; this file mixes one sync test with async ones.


async def _create_brand(db_session, **overrides) -> Brand:
    suffix = uuid4().hex[:10]
    defaults = {
        "id": uuid4(),
        "name": f"Test Brand {suffix}",
        "slug": f"test-brand-{suffix}",
        "custom_domain": None,
        "chatbot_config": None,
        "landing_page_tier_config": None,
        "is_active": True,
    }
    defaults.update(overrides)
    brand = Brand(**defaults)
    db_session.add(brand)
    await db_session.commit()
    await db_session.refresh(brand)
    return brand


async def _user_with_brand_permission(db_session, *, action: str) -> User:
    """Persisted non-superuser User assigned a freshly-created Role that grants
    the migration-056-seeded ("brands", action) permission. Everything here
    (Role, RolePermission, User.role_id) is written through the ORM in this
    same test run, unlike the migration-raw-SQL-seeded rows
    `SQLITE_ROLE_UUID_DASH_BUG_REASON` describes -- exercises the real
    `require_permission()` -> `user_has_permission()` -> RolePermission join,
    not the `is_superuser` bypass.
    """
    from app.modules.admin import repository as admin_repository
    from app.modules.admin.models import Permission

    result = await db_session.execute(
        select(Permission).where(Permission.resource == "brands", Permission.action == action)
    )
    permission = result.scalar_one()

    role = await admin_repository.create_role(
        db_session, name=f"brand-{action}-tester-{uuid4().hex[:8]}", description=None
    )
    await admin_repository.attach_permission(
        db_session, role_id=role.id, permission_id=permission.id
    )

    user = User(
        id=uuid4(),
        email=f"brand-{action}-tester-{uuid4().hex[:8]}@example.com",
        first_name="Brand",
        last_name="Tester",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        role_id=role.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# GET /api/admin/brands
# ---------------------------------------------------------------------------


async def test_list_brands_returns_active_and_inactive_brands(
    client, superuser, auth_headers, db_session
):
    """Confirms the router calls `list_all_brands` (unfiltered), not
    `list_active_brands` -- an inactive brand must still show up here."""
    active = await _create_brand(db_session, is_active=True)
    inactive = await _create_brand(db_session, is_active=False)

    response = client.get("/api/admin/brands", headers=auth_headers(superuser.id))
    body = assert_success(response, status=200)

    ids = {row["id"] for row in body}
    assert str(active.id) in ids
    assert str(inactive.id) in ids
    inactive_row = next(row for row in body if row["id"] == str(inactive.id))
    assert inactive_row["is_active"] is False


async def test_list_brands_403_without_brands_read_permission(client, regular_user, auth_headers):
    response = client.get("/api/admin/brands", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


@pytest.mark.xfail(
    condition=not USING_POSTGRES, reason=SQLITE_ROLE_UUID_DASH_BUG_REASON, strict=True
)
async def test_list_brands_succeeds_with_real_brands_read_grant(client, db_session, auth_headers):
    """Same endpoint as above, but the granted user is a genuine non-superuser
    RBAC grant (see `_user_with_brand_permission`) rather than the
    `is_superuser` bypass. Empirically returns 403 on SQLite even though the
    grant is set up correctly -- confirmed by running this test in isolation
    (see the module's `SQLITE_ROLE_UUID_DASH_BUG_REASON` import). This is the
    same class of pre-existing, documented SQLite-only dashed/undashed UUID
    mismatch `test_admin_rbac.py`'s `support_user` tests hit, here triggered
    via `056_seed_brands_permissions.py`'s raw-SQL-seeded ("brands", "read")
    Permission row instead of migration 038's raw-SQL-seeded Role row -- not
    a bug in `app/modules/brands/`. xfail is conditional on `not
    USING_POSTGRES` so this would run for real (not silently skip) if this
    suite is ever run against Postgres."""
    brand = await _create_brand(db_session)
    reader = await _user_with_brand_permission(db_session, action="read")

    response = client.get("/api/admin/brands", headers=auth_headers(reader.id))
    body = assert_success(response, status=200)
    assert str(brand.id) in {row["id"] for row in body}


# ---------------------------------------------------------------------------
# POST /api/admin/brands
# ---------------------------------------------------------------------------


async def test_create_brand_succeeds_for_user_with_brands_write_permission(
    client, superuser, auth_headers
):
    suffix = uuid4().hex[:8]
    payload = {
        "name": f"Acme Careers {suffix}",
        "slug": f"acme-careers-{suffix}",
        "custom_domain": "careers.acme.example",
        "chatbot_config": {"tone": "friendly"},
        "landing_page_tier_config": {"tiers": ["senior", "mid"]},
    }

    response = client.post("/api/admin/brands", json=payload, headers=auth_headers(superuser.id))
    body = assert_success(response, status=201)

    assert body["name"] == payload["name"]
    assert body["slug"] == payload["slug"]
    assert body["custom_domain"] == payload["custom_domain"]
    assert body["chatbot_config"] == payload["chatbot_config"]
    assert body["landing_page_tier_config"] == payload["landing_page_tier_config"]
    assert body["is_active"] is True
    assert body["id"] is not None

    # Persistence check: a brand-new HTTP request gets its own DB session
    # (app/database/session.py's `get_db_session` opens a fresh
    # `SessionLocal()` per request), the same as a real second client would.
    # This is the only way this suite can observe whether `create_brand`
    # actually committed, as opposed to only flushing within the original
    # request's own session/transaction.
    followup = client.get(f"/api/admin/brands/{body['id']}", headers=auth_headers(superuser.id))
    followup_body = assert_success(followup, status=200)
    assert followup_body["name"] == payload["name"]


async def test_create_brand_403_without_brands_write_permission(client, regular_user, auth_headers):
    response = client.post(
        "/api/admin/brands",
        json={"name": "Should Not Be Created", "slug": "should-not-be-created"},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)


async def test_create_brand_409_on_duplicate_slug(client, superuser, auth_headers, db_session):
    existing = await _create_brand(db_session)
    payload = {
        "name": "Duplicate Slug Brand",
        "slug": existing.slug,
    }

    response = client.post("/api/admin/brands", json=payload, headers=auth_headers(superuser.id))
    assert_error(response, 409)


# ---------------------------------------------------------------------------
# GET /api/admin/brands/{brand_id}
# ---------------------------------------------------------------------------


async def test_get_brand_returns_single_brand(client, superuser, auth_headers, db_session):
    brand = await _create_brand(db_session)

    response = client.get(f"/api/admin/brands/{brand.id}", headers=auth_headers(superuser.id))
    body = assert_success(response, status=200)

    assert body["id"] == str(brand.id)
    assert body["name"] == brand.name
    assert body["slug"] == brand.slug


async def test_get_brand_404_for_unknown_id(client, superuser, auth_headers):
    response = client.get(f"/api/admin/brands/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


async def test_get_brand_403_without_brands_read_permission(
    client, regular_user, auth_headers, db_session
):
    brand = await _create_brand(db_session)

    response = client.get(f"/api/admin/brands/{brand.id}", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


# ---------------------------------------------------------------------------
# PATCH /api/admin/brands/{brand_id}
# ---------------------------------------------------------------------------


async def test_update_brand_updates_allowed_fields(client, superuser, auth_headers, db_session):
    brand = await _create_brand(
        db_session,
        custom_domain=None,
        chatbot_config=None,
        landing_page_tier_config=None,
    )
    suffix = uuid4().hex[:8]
    payload = {
        "name": f"Renamed Brand {suffix}",
        "slug": f"renamed-brand-{suffix}",
        "custom_domain": "jobs.renamed.example",
        "chatbot_config": {"tone": "formal", "greeting": "Welcome"},
        "landing_page_tier_config": {"tiers": ["junior"]},
    }

    response = client.patch(
        f"/api/admin/brands/{brand.id}", json=payload, headers=auth_headers(superuser.id)
    )
    body = assert_success(response, status=200)

    assert body["name"] == payload["name"]
    assert body["slug"] == payload["slug"]
    assert body["custom_domain"] == payload["custom_domain"]
    assert body["chatbot_config"] == payload["chatbot_config"]
    assert body["landing_page_tier_config"] == payload["landing_page_tier_config"]

    # Persistence check via a brand-new HTTP request/DB session -- see the
    # comment on `test_create_brand_succeeds_for_user_with_brands_write_permission`
    # above for why `db_session.refresh(brand)` is not a reliable check here.
    followup = client.get(f"/api/admin/brands/{brand.id}", headers=auth_headers(superuser.id))
    followup_body = assert_success(followup, status=200)
    assert followup_body["name"] == payload["name"]
    assert followup_body["slug"] == payload["slug"]


async def test_update_brand_404_for_unknown_id(client, superuser, auth_headers):
    response = client.patch(
        f"/api/admin/brands/{uuid4()}",
        json={"name": "does not matter"},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 404)


async def test_update_brand_403_without_brands_write_permission(
    client, regular_user, auth_headers, db_session
):
    brand = await _create_brand(db_session)

    response = client.patch(
        f"/api/admin/brands/{brand.id}",
        json={"name": "attempted update"},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)


async def test_update_brand_409_when_slug_belongs_to_another_brand(
    client, superuser, auth_headers, db_session
):
    owner = await _create_brand(db_session)
    other = await _create_brand(db_session)

    response = client.patch(
        f"/api/admin/brands/{other.id}",
        json={"slug": owner.slug},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 409)


@pytest.mark.xfail(
    condition=not USING_POSTGRES, reason=SQLITE_ROLE_UUID_DASH_BUG_REASON, strict=True
)
async def test_update_brand_succeeds_with_real_brands_write_grant(client, db_session, auth_headers):
    """Same endpoint as `test_update_brand_updates_allowed_fields`, but exercises
    the real, non-superuser RBAC grant path (see `_user_with_brand_permission`).
    Same pre-existing SQLite-only dashed/undashed UUID join bug as
    `test_list_brands_succeeds_with_real_brands_read_grant` above."""
    brand = await _create_brand(db_session)
    writer = await _user_with_brand_permission(db_session, action="write")

    response = client.patch(
        f"/api/admin/brands/{brand.id}",
        json={"name": "Updated By RBAC Writer"},
        headers=auth_headers(writer.id),
    )
    body = assert_success(response, status=200)
    assert body["name"] == "Updated By RBAC Writer"


# ---------------------------------------------------------------------------
# RELEASE-BLOCKING: is_active can never be set through this endpoint.
# ---------------------------------------------------------------------------


def test_brand_update_request_schema_has_no_is_active_field():
    """Structural guard: `BrandUpdateRequest` must never grow an `is_active`
    field. Deactivation is BD's separate audited flow
    (post-tenancy-features/03-org-offboarding-and-deletion.md), not a plain
    field edit through PATCH /api/admin/brands/{id}."""
    from app.modules.brands.router import BrandUpdateRequest

    assert "is_active" not in BrandUpdateRequest.model_fields


async def test_update_brand_ignores_is_active_in_request_body(
    client, superuser, auth_headers, db_session
):
    """Even though `BrandUpdateRequest` has no `is_active` field (see the
    schema-level test above), also verify at the HTTP layer that passing
    `is_active` in the raw JSON body has zero effect on the persisted brand --
    pydantic silently drops unknown fields by default, so this asserts that
    behavior end to end rather than merely trusting it."""
    brand = await _create_brand(db_session, is_active=True)

    response = client.patch(
        f"/api/admin/brands/{brand.id}",
        json={"is_active": False, "name": "Still Active After Patch"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response, status=200)

    assert body["name"] == "Still Active After Patch"
    assert body["is_active"] is True

    await db_session.refresh(brand)
    assert brand.is_active is True


async def test_deactivated_brand_stays_deactivated_across_unrelated_patch(
    client, superuser, auth_headers, db_session
):
    """Mirror of the above for a brand that starts inactive: an unrelated PATCH
    (and even an explicit `is_active: true` attempt) must not reactivate it
    through this endpoint."""
    brand = await _create_brand(db_session, is_active=False)

    response = client.patch(
        f"/api/admin/brands/{brand.id}",
        json={"is_active": True, "custom_domain": "still-inactive.example"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response, status=200)

    assert body["custom_domain"] == "still-inactive.example"
    assert body["is_active"] is False

    await db_session.refresh(brand)
    assert brand.is_active is False
