"""Admin visibility into job_swipe_actions: cursor-paginated list with filters
and joined job-posting context, detail endpoint, RBAC gate (`job_swipe:read`,
migration 041), and confirmation that no moderate/mutate route exists at all —
swipe/match records are interaction data, not published content, so this
resource deliberately has no moderate action (not even a stub)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.conftest import SQLITE_ROLE_UUID_DASH_BUG_REASON, USING_POSTGRES
from tests.envelope_helpers import assert_error, assert_success

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` here — this file
# mixes sync (`test_router_defines_no_mutating_routes`) and async test
# functions, and pyproject.toml's asyncio_mode = "auto" already handles async
# def tests automatically; applying the marker to the whole module also
# (harmlessly, but noisily) tags the sync test, which pytest-asyncio warns
# about. Same convention as test_admin_rbac.py.


@pytest.fixture(autouse=True)
def _mount_job_swipe_router():
    """`job_swipe_router` is not wired into `app/modules/admin/__init__.py` yet
    (that aggregator is held back and wired centrally later, out of scope for
    this chunk) — mount it directly onto the app for this test module only,
    matching `test_api_envelopes.py`'s temporary-mount-and-unmount pattern.
    The router's own `require_permission` dependency already enforces
    authentication/authorization, so no extra `current_verified_user`
    dependency is needed here."""
    from app.main import app
    from app.modules.admin.job_swipe_router import router as job_swipe_router

    app.include_router(job_swipe_router)
    try:
        yield
    finally:
        prefix = job_swipe_router.prefix
        app.routes[:] = [
            route for route in app.routes if not getattr(route, "path", "").startswith(prefix)
        ]


@pytest.fixture
async def seeded_swipe_actions(db_session, regular_user):
    """Two swipe actions by `regular_user` on two distinct JobPosting/JobMatch
    rows — one 'right', one 'left' — so filter and join-context assertions
    have deterministic, distinguishable rows to check against."""
    from app.modules.job_matching.models import JobMatch, JobPosting
    from app.modules.job_swipe.models import JobSwipeAction

    suffix = uuid4().hex[:8]
    postings = []
    for i in range(2):
        posting = JobPosting(
            dedup_key=f"dedup-{suffix}-{i}",
            title=f"Backend Engineer {suffix}-{i}",
            company=f"Acme Corp {suffix}-{i}",
            source="linkedin",
        )
        db_session.add(posting)
        postings.append(posting)
    await db_session.commit()
    for posting in postings:
        await db_session.refresh(posting)

    matches = []
    for posting in postings:
        match = JobMatch(
            user_id=regular_user.id,
            job_posting_id=posting.id,
            similarity_score=0.8,
            rule_score=0.7,
            overall_score=75.0,
        )
        db_session.add(match)
        matches.append(match)
    await db_session.commit()
    for match in matches:
        await db_session.refresh(match)

    directions = ["right", "left"]
    swipes = []
    for match, direction in zip(matches, directions, strict=True):
        swipe = JobSwipeAction(job_match_id=match.id, user_id=regular_user.id, direction=direction)
        db_session.add(swipe)
        swipes.append(swipe)
    await db_session.commit()
    for swipe in swipes:
        await db_session.refresh(swipe)

    return list(zip(swipes, postings, strict=True))


async def test_list_requires_authentication(client):
    response = client.get("/api/admin/job-swipe")
    assert response.status_code == 401


async def test_list_regular_user_forbidden(client, regular_user, auth_headers):
    """A plain user (no role, not superuser) has no `job_swipe:read` permission."""
    response = client.get("/api/admin/job-swipe", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


@pytest.mark.xfail(
    condition=not USING_POSTGRES, reason=SQLITE_ROLE_UUID_DASH_BUG_REASON, strict=True
)
async def test_support_role_can_list(client, support_user, auth_headers):
    """migration 041 grants `job_swipe:read` (a READ_ONLY_ACTIONS entry) to the
    seeded 'support' role — RBAC path, not the is_superuser bypass."""
    response = client.get("/api/admin/job-swipe", headers=auth_headers(support_user.id))
    assert_success(response)


async def test_list_returns_joined_job_posting_context(
    client, superuser, auth_headers, seeded_swipe_actions
):
    response = client.get("/api/admin/job-swipe", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body

    by_id = {item["id"]: item for item in body["items"]}
    for swipe, posting in seeded_swipe_actions:
        item = by_id[str(swipe.id)]
        assert item["job_match_id"] == str(swipe.job_match_id)
        assert item["user_id"] == str(swipe.user_id)
        assert item["direction"] == swipe.direction
        assert item["job_posting_id"] == str(posting.id)
        assert item["job_posting_title"] == posting.title
        assert item["job_posting_company"] == posting.company


async def test_list_filters_by_direction(client, superuser, auth_headers, seeded_swipe_actions):
    response = client.get(
        "/api/admin/job-swipe",
        params={"direction": "right"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)

    right_swipe_ids = {
        str(swipe.id) for swipe, _ in seeded_swipe_actions if swipe.direction == "right"
    }
    returned_ids = {item["id"] for item in body["items"]}
    assert right_swipe_ids <= returned_ids
    assert all(item["direction"] == "right" for item in body["items"])


async def test_list_filters_by_user_id(
    client, superuser, regular_user, auth_headers, seeded_swipe_actions
):
    response = client.get(
        "/api/admin/job-swipe",
        params={"user_id": str(regular_user.id)},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert len(body["items"]) >= len(seeded_swipe_actions)
    assert all(item["user_id"] == str(regular_user.id) for item in body["items"])


async def test_detail_endpoint_returns_joined_context(
    client, superuser, auth_headers, seeded_swipe_actions
):
    swipe, posting = seeded_swipe_actions[0]
    response = client.get(f"/api/admin/job-swipe/{swipe.id}", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert body["id"] == str(swipe.id)
    assert body["job_posting_id"] == str(posting.id)
    assert body["job_posting_title"] == posting.title
    assert body["job_posting_company"] == posting.company


async def test_detail_endpoint_requires_permission(
    client, regular_user, auth_headers, seeded_swipe_actions
):
    swipe, _ = seeded_swipe_actions[0]
    response = client.get(f"/api/admin/job-swipe/{swipe.id}", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_detail_endpoint_404_for_unknown_id(client, superuser, auth_headers):
    response = client.get(f"/api/admin/job-swipe/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


def test_router_defines_no_mutating_routes():
    """Deliberate design per the plan: no moderate/mutate action exists for
    `job_swipe` at all (migration 041 seeds only `job_swipe:read`, with no
    matching `job_swipe:moderate`). Assert this at the route-table level, not
    just by absence of a handler in this file."""
    from app.modules.admin.job_swipe_router import router

    all_methods: set[str] = set()
    for route in router.routes:
        all_methods |= set(getattr(route, "methods", None) or set())
    assert all_methods
    assert all_methods <= {"GET", "HEAD"}


async def test_no_post_route_on_list_path(client, superuser, auth_headers):
    """The list path exists (GET), but no POST handler was ever registered for
    it — the router's route table only allows GET/HEAD there."""
    response = client.post("/api/admin/job-swipe", headers=auth_headers(superuser.id))
    assert response.status_code == 405


async def test_no_moderate_route_exists(client, superuser, auth_headers):
    """Confirms the read-only design intent is actually enforced end-to-end —
    not merely absent from this file by omission — by asserting the
    plan-shaped moderate endpoint doesn't resolve to any route at all."""
    response = client.post(
        f"/api/admin/job-swipe/{uuid4()}/moderate", headers=auth_headers(superuser.id)
    )
    assert response.status_code == 404
