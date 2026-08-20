"""Admin job postings moderation endpoints: list/detail/moderate + RBAC gate
(migrations 039-041, Admin Module Phase 2 moderation layer — Batch 1).

`app.modules.admin.job_postings_router` is not yet wired into
`app.modules.admin.__init__` (held back for central wiring across all
Batch-1 chunks — see plan), so this module mounts it onto the shared `app`
for the duration of each test, mirroring the temporary-route pattern already
used in test_api_envelopes.py / test_error_tracking.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.admin.job_postings_router import router as job_postings_router
from app.modules.admin.models import AdminAuditLog
from app.modules.job_matching.models import JobPosting
from tests.conftest import SQLITE_ROLE_UUID_DASH_BUG_REASON, USING_POSTGRES
from tests.envelope_helpers import assert_error, assert_success

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — see
# test_admin_rbac.py's comment; this repo's pyproject.toml sets
# asyncio_mode = "auto" already, and every test here is `async def`.


@pytest.fixture(autouse=True)
def _mount_job_postings_router():
    """Mount the not-yet-wired router onto the shared `app` for this test
    only, then unmount so other test modules see the app as it ships today
    (without this chunk's router included via __init__.py)."""
    from app.main import app

    app.include_router(job_postings_router)
    try:
        yield
    finally:
        app.routes[:] = [
            route
            for route in app.routes
            if not getattr(route, "path", "").startswith("/api/admin/job-postings")
        ]


async def _make_job_posting(db_session, /, **overrides) -> JobPosting:
    defaults = {
        "dedup_key": f"dedup-{uuid4().hex}",
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "remote": True,
        "source": "linkedin",
        "source_url": "https://example.com/job",
        "salary_min": 100_000,
        "salary_max": 140_000,
        "salary_currency": "USD",
    }
    defaults.update(overrides)
    posting = JobPosting(**defaults)
    db_session.add(posting)
    await db_session.commit()
    await db_session.refresh(posting)
    return posting


async def test_list_job_postings_requires_authentication(client):
    response = client.get("/api/admin/job-postings")
    assert response.status_code == 401


async def test_list_job_postings_regular_user_forbidden(client, regular_user, auth_headers):
    response = client.get("/api/admin/job-postings", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_list_job_postings_returns_cursor_shape(client, superuser, auth_headers, db_session):
    await _make_job_posting(db_session)
    response = client.get("/api/admin/job-postings", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body
    assert len(body["items"]) >= 1


async def test_list_job_postings_filters_by_moderation_status(
    client, superuser, auth_headers, db_session
):
    suffix = uuid4().hex[:8]
    active = await _make_job_posting(db_session, dedup_key=f"active-{suffix}")
    hidden = await _make_job_posting(
        db_session, dedup_key=f"hidden-{suffix}", moderation_status="hidden"
    )

    response = client.get(
        "/api/admin/job-postings",
        params={"moderation_status": "hidden"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(hidden.id) in ids
    assert str(active.id) not in ids


async def test_list_job_postings_filters_by_source_and_is_active(
    client, superuser, auth_headers, db_session
):
    suffix = uuid4().hex[:8]
    matching = await _make_job_posting(
        db_session, dedup_key=f"match-{suffix}", source=f"indeed-{suffix}", is_active=True
    )
    other_source = await _make_job_posting(
        db_session,
        dedup_key=f"other-source-{suffix}",
        source=f"linkedin-{suffix}",
        is_active=True,
    )
    inactive = await _make_job_posting(
        db_session, dedup_key=f"inactive-{suffix}", source=f"indeed-{suffix}", is_active=False
    )

    response = client.get(
        "/api/admin/job-postings",
        params={"source": f"indeed-{suffix}", "is_active": True},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(matching.id) in ids
    assert str(other_source.id) not in ids
    assert str(inactive.id) not in ids


async def test_get_job_posting_detail(client, superuser, auth_headers, db_session):
    posting = await _make_job_posting(db_session)
    response = client.get(
        f"/api/admin/job-postings/{posting.id}", headers=auth_headers(superuser.id)
    )
    body = assert_success(response)
    assert body["id"] == str(posting.id)
    assert body["moderation_status"] == "active"


async def test_get_job_posting_detail_404(client, superuser, auth_headers):
    response = client.get(f"/api/admin/job-postings/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


async def test_moderate_job_posting_happy_path(client, superuser, auth_headers, db_session):
    posting = await _make_job_posting(db_session)

    response = client.post(
        f"/api/admin/job-postings/{posting.id}/moderate",
        json={"moderation_status": "hidden", "reason": "Spam report"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert body["moderation_status"] == "hidden"
    assert body["moderated_by"] == str(superuser.id)
    assert body["moderated_at"] is not None

    await db_session.refresh(posting)
    assert posting.moderation_status == "hidden"
    assert posting.moderated_by == superuser.id
    assert posting.moderated_at is not None

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "job_postings.moderate",
            AdminAuditLog.target_id == str(posting.id),
        )
    )
    entry = result.scalar_one()
    assert entry.actor_user_id == superuser.id
    assert entry.target_type == "job_posting"
    assert entry.before["moderation_status"] == "active"
    assert entry.after["moderation_status"] == "hidden"
    assert entry.after["reason"] == "Spam report"


async def test_moderate_job_posting_404(client, superuser, auth_headers):
    response = client.post(
        f"/api/admin/job-postings/{uuid4()}/moderate",
        json={"moderation_status": "hidden", "reason": None},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 404)


async def test_moderate_job_posting_requires_moderate_permission_for_regular_user(
    client, regular_user, auth_headers, db_session
):
    posting = await _make_job_posting(db_session)
    response = client.post(
        f"/api/admin/job-postings/{posting.id}/moderate",
        json={"moderation_status": "hidden", "reason": None},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)


@pytest.mark.xfail(
    condition=not USING_POSTGRES, reason=SQLITE_ROLE_UUID_DASH_BUG_REASON, strict=True
)
async def test_support_role_can_read_but_not_moderate(
    client, support_user, auth_headers, db_session
):
    """migration 041 grants 'support' job_postings:read but NOT
    job_postings:moderate."""
    posting = await _make_job_posting(db_session)

    list_response = client.get("/api/admin/job-postings", headers=auth_headers(support_user.id))
    assert_success(list_response)

    detail_response = client.get(
        f"/api/admin/job-postings/{posting.id}", headers=auth_headers(support_user.id)
    )
    assert_success(detail_response)

    moderate_response = client.post(
        f"/api/admin/job-postings/{posting.id}/moderate",
        json={"moderation_status": "hidden", "reason": None},
        headers=auth_headers(support_user.id),
    )
    assert_error(moderate_response, 403)
