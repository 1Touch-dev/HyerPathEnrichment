"""Admin visibility into application-lifecycle status (`JobMatch`): list/
detail + RBAC gate + filters (migration 046, Admin Module — Module 4
admin visibility surface). No moderate endpoint exists for this resource
(user-authored self-reporting, not moderatable content) — see the
module docstring in `applications_router.py`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
async def seeded_applications(db_session, regular_user):
    """Two `JobMatch` rows for `regular_user`: one backed by a `JobPosting`
    (job_posting_id set), one a manual entry (manual_job_entry_id set) — so
    the outer-join and null-linkage paths both have deterministic rows."""
    from app.modules.job_matching.models import JobMatch, JobPosting
    from app.modules.manual_jobs.models import ManualJobEntry

    suffix = uuid4().hex[:8]
    posting = JobPosting(
        dedup_key=f"dedup-{suffix}",
        title=f"Backend Engineer {suffix}",
        company=f"Acme Corp {suffix}",
        source="linkedin",
    )
    db_session.add(posting)
    manual_entry = ManualJobEntry(
        user_id=regular_user.id,
        title=f"Manual Role {suffix}",
        company=f"Manual Co {suffix}",
    )
    db_session.add(manual_entry)
    await db_session.commit()
    await db_session.refresh(posting)
    await db_session.refresh(manual_entry)

    posting_match = JobMatch(
        user_id=regular_user.id,
        job_posting_id=posting.id,
        similarity_score=0.8,
        rule_score=0.7,
        overall_score=75.0,
        application_status="applied",
    )
    manual_match = JobMatch(
        user_id=regular_user.id,
        manual_job_entry_id=manual_entry.id,
        similarity_score=0.6,
        rule_score=0.5,
        overall_score=55.0,
        application_status="new",
    )
    db_session.add(posting_match)
    db_session.add(manual_match)
    await db_session.commit()
    await db_session.refresh(posting_match)
    await db_session.refresh(manual_match)

    return {
        "posting": posting,
        "posting_match": posting_match,
        "manual_entry": manual_entry,
        "manual_match": manual_match,
    }


async def test_list_applications_requires_authentication(client):
    response = client.get("/api/admin/applications")
    assert response.status_code == 401


async def test_list_applications_regular_user_forbidden(client, regular_user, auth_headers):
    response = client.get("/api/admin/applications", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_support_role_can_list(client, support_user, auth_headers):
    """migration 046 grants `applications:read` to the seeded 'support' role."""
    response = client.get("/api/admin/applications", headers=auth_headers(support_user.id))
    assert_success(response)


async def test_list_applications_returns_cursor_shape_and_joined_context(
    client, superuser, auth_headers, seeded_applications
):
    response = client.get("/api/admin/applications", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body

    by_id = {item["id"]: item for item in body["items"]}
    posting_match = seeded_applications["posting_match"]
    posting = seeded_applications["posting"]
    manual_match = seeded_applications["manual_match"]

    posting_item = by_id[str(posting_match.id)]
    assert posting_item["job_posting_id"] == str(posting.id)
    assert posting_item["job_posting_title"] == posting.title
    assert posting_item["job_posting_company"] == posting.company
    assert posting_item["manual_job_entry_id"] is None
    assert posting_item["application_status"] == "applied"

    manual_item = by_id[str(manual_match.id)]
    assert manual_item["job_posting_id"] is None
    assert manual_item["job_posting_title"] is None
    assert manual_item["manual_job_entry_id"] == str(seeded_applications["manual_entry"].id)
    assert manual_item["application_status"] == "new"


async def test_list_applications_filters_by_application_status(
    client, superuser, auth_headers, seeded_applications
):
    response = client.get(
        "/api/admin/applications",
        params={"application_status": "new"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(seeded_applications["manual_match"].id) in ids
    assert str(seeded_applications["posting_match"].id) not in ids


async def test_list_applications_filters_by_user_id(
    client, superuser, regular_user, auth_headers, seeded_applications
):
    response = client.get(
        "/api/admin/applications",
        params={"user_id": str(regular_user.id)},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert len(body["items"]) >= 2
    assert all(item["user_id"] == str(regular_user.id) for item in body["items"])


async def test_get_application_detail(client, superuser, auth_headers, seeded_applications):
    posting_match = seeded_applications["posting_match"]
    response = client.get(
        f"/api/admin/applications/{posting_match.id}", headers=auth_headers(superuser.id)
    )
    body = assert_success(response)
    assert body["id"] == str(posting_match.id)
    assert body["application_status"] == "applied"


async def test_get_application_detail_404(client, superuser, auth_headers):
    response = client.get(f"/api/admin/applications/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


async def test_get_application_detail_requires_permission(
    client, regular_user, auth_headers, seeded_applications
):
    posting_match = seeded_applications["posting_match"]
    response = client.get(
        f"/api/admin/applications/{posting_match.id}", headers=auth_headers(regular_user.id)
    )
    assert_error(response, 403)


def test_router_defines_no_mutating_routes():
    """Deliberate design: no moderate/mutate action exists for `applications`
    at all — application-lifecycle status is user-authored self-reporting."""
    from app.modules.admin.applications_router import router

    all_methods: set[str] = set()
    for route in router.routes:
        all_methods |= set(getattr(route, "methods", None) or set())
    assert all_methods
    assert all_methods <= {"GET", "HEAD"}
