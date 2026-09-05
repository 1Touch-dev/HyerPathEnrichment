"""HTTP tests for the job matching router endpoints (via TestClient)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.main import app
from app.modules.job_matching import events as job_matching_events
from app.modules.job_matching.models import JobMatch, JobPosting, PushSubscription
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _auth_headers(user_id: str | None = None) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": user_id or str(uuid4()),
    }


@pytest.fixture
async def seeded_match(db: AsyncSession) -> dict[str, Any]:
    """Insert a User + JobPosting + JobMatch directly, bypassing service/repository layers."""
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"seeded-{user_id.hex[:8]}@example.com",
        first_name="Seeded",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)

    posting = JobPosting(
        dedup_key=f"dedup-{uuid4().hex}",
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="Remote",
        remote=True,
        source="linkedin",
        source_url="https://linkedin.com/jobs/123",
        salary_min=120_000,
        salary_max=160_000,
        salary_currency="USD",
    )
    db.add(posting)
    await db.commit()
    await db.refresh(posting)

    match = JobMatch(
        user_id=user_id,
        job_posting_id=posting.id,
        similarity_score=0.9,
        rule_score=0.8,
        overall_score=86.0,
        score_breakdown={"salary_fit": 1.0, "location_fit": 1.0},
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)

    return {"user_id": user_id, "posting": posting, "match": match}


# ---------------------------------------------------------------------------
# GET /api/job-matching/preferences
# ---------------------------------------------------------------------------


def test_get_preferences_404_when_not_set(client: TestClient) -> None:
    response = client.get("/api/job-matching/preferences", headers=_auth_headers())
    body = assert_error(response, 404, "NOT_FOUND")
    assert body["error"]["message"] == "Preferences not set"


# ---------------------------------------------------------------------------
# PUT /api/job-matching/preferences
# ---------------------------------------------------------------------------


def test_put_preferences_creates_with_defaults(client: TestClient) -> None:
    headers = _auth_headers()
    payload = {
        "desired_roles": ["Software Engineer", "Backend Engineer"],
        "desired_locations": ["New York, NY"],
        "remote_preference": "remote",
        "salary_min": 100_000,
        "salary_max": 150_000,
    }

    response = client.put("/api/job-matching/preferences", headers=headers, json=payload)
    data = assert_success(response)

    assert data["desired_roles"] == payload["desired_roles"]
    assert data["desired_locations"] == payload["desired_locations"]
    assert data["remote_preference"] == "remote"
    assert data["salary_min"] == 100_000
    assert data["salary_max"] == 150_000
    assert data["salary_currency"] == "USD"
    assert data["notification_channels"] == ["email"]
    assert data["digest_frequency"] == "daily"
    assert data["is_scan_enabled"] is True
    assert data["user_id"] == headers["X-Test-User-ID"]
    assert data["source_document_id"] is None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_put_preferences_upsert_updates_existing_row(client: TestClient) -> None:
    headers = _auth_headers()

    first = client.put(
        "/api/job-matching/preferences",
        headers=headers,
        json={"desired_roles": ["Engineer"], "salary_min": 80_000},
    )
    first_data = assert_success(first)

    second = client.put(
        "/api/job-matching/preferences",
        headers=headers,
        json={"desired_roles": ["Senior Engineer"], "salary_min": 120_000},
    )
    second_data = assert_success(second)

    # Same row (same user_id, same primary identity) updated, not duplicated.
    assert second_data["user_id"] == first_data["user_id"]

    fetched = client.get("/api/job-matching/preferences", headers=headers)
    fetched_data = assert_success(fetched)
    assert fetched_data["desired_roles"] == ["Senior Engineer"]
    assert fetched_data["salary_min"] == 120_000


def test_put_preferences_rejects_salary_max_below_min(client: TestClient) -> None:
    response = client.put(
        "/api/job-matching/preferences",
        headers=_auth_headers(),
        json={"salary_min": 150_000, "salary_max": 100_000},
    )
    assert response.status_code == 422


def test_put_preferences_partial_update_preserves_omitted_fields(client: TestClient) -> None:
    """Regression test for the destructive-overwrite bug (Fix 4a): a PUT that only
    changes `salary_min` must not reset `desired_roles` (or any other omitted field)
    back to its schema default. Before the fix, `service.py` called `payload.model_dump()`
    (no `exclude_unset`), so every omitted field was silently overwritten on every save.
    """
    headers = _auth_headers()

    first = client.put(
        "/api/job-matching/preferences",
        headers=headers,
        json={
            "desired_roles": ["Engineer"],
            "desired_locations": ["Remote"],
            "notification_channels": ["email"],
            "digest_frequency": "weekly",
        },
    )
    first_data = assert_success(first)
    assert first_data["desired_roles"] == ["Engineer"]
    assert first_data["digest_frequency"] == "weekly"

    # Only salary_min is sent this time — everything else should be left untouched.
    second = client.put(
        "/api/job-matching/preferences",
        headers=headers,
        json={"salary_min": 90_000},
    )
    second_data = assert_success(second)

    assert second_data["salary_min"] == 90_000
    assert second_data["desired_roles"] == ["Engineer"]
    assert second_data["desired_locations"] == ["Remote"]
    assert second_data["notification_channels"] == ["email"]
    assert second_data["digest_frequency"] == "weekly"


# ---------------------------------------------------------------------------
# GET /api/job-matching/matches
# ---------------------------------------------------------------------------


def test_list_matches_empty_for_new_user(client: TestClient) -> None:
    response = client.get("/api/job-matching/matches", headers=_auth_headers())
    data = assert_success(response)

    assert data["matches"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_list_matches_returns_seeded_match(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))

    response = client.get("/api/job-matching/matches", headers=headers)
    data = assert_success(response)

    assert data["total"] == 1
    assert len(data["matches"]) == 1

    match_payload = data["matches"][0]
    posting = seeded_match["posting"]
    match = seeded_match["match"]

    assert match_payload["match_id"] == str(match.id)
    assert match_payload["job_posting_id"] == str(posting.id)
    assert match_payload["title"] == "Senior Backend Engineer"
    assert match_payload["company"] == "Acme Corp"
    assert match_payload["overall_score"] == 86.0
    assert match_payload["is_new"] is True  # notified_at is None
    assert match_payload["viewed_at"] is None
    assert match_payload["feedback"] is None


# ---------------------------------------------------------------------------
# POST /api/job-matching/matches/{match_id}/view
# ---------------------------------------------------------------------------


def test_mark_match_viewed_success(client: TestClient, seeded_match: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.post(f"/api/job-matching/matches/{match_id}/view", headers=headers)
    assert response.status_code == 204


def test_mark_match_viewed_bogus_id_returns_404(client: TestClient) -> None:
    headers = _auth_headers()
    bogus_id = str(uuid4())

    response = client.post(f"/api/job-matching/matches/{bogus_id}/view", headers=headers)
    body = assert_error(response, 404, "NOT_FOUND")
    assert body["error"]["message"] == "Match not found"


def test_mark_match_viewed_other_users_match_returns_404(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    other_user_headers = _auth_headers()  # different (fresh) user id
    match_id = str(seeded_match["match"].id)

    response = client.post(f"/api/job-matching/matches/{match_id}/view", headers=other_user_headers)
    assert_error(response, 404, "NOT_FOUND")


# ---------------------------------------------------------------------------
# POST /api/job-matching/matches/{match_id}/feedback
# ---------------------------------------------------------------------------


def test_submit_match_feedback_success(client: TestClient, seeded_match: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.post(
        f"/api/job-matching/matches/{match_id}/feedback",
        headers=headers,
        json={"feedback": "up"},
    )
    assert response.status_code == 204


def test_submit_match_feedback_invalid_value_returns_422(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.post(
        f"/api/job-matching/matches/{match_id}/feedback",
        headers=headers,
        json={"feedback": "maybe"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/job-matching/matches/{match_id}/apply-redirect
# POST /api/job-matching/matches/{match_id}/mark-applied
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_match_without_source_url(db: AsyncSession) -> dict[str, Any]:
    """A match whose posting has no source_url (should never normally happen for
    scraped postings, but defensively 404s rather than redirecting nowhere)."""
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"seeded-no-url-{user_id.hex[:8]}@example.com",
        first_name="Seeded",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)

    posting = JobPosting(
        dedup_key=f"dedup-{uuid4().hex}",
        title="Manual Entry",
        company="Acme Corp",
        location="Remote",
        remote=True,
        source="manual",
        source_url=None,
    )
    db.add(posting)
    await db.commit()
    await db.refresh(posting)

    match = JobMatch(
        user_id=user_id,
        job_posting_id=posting.id,
        similarity_score=0.9,
        rule_score=0.8,
        overall_score=86.0,
        score_breakdown={},
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)

    return {"user_id": user_id, "posting": posting, "match": match}


def test_apply_redirect_success_302s_to_stored_source_url(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.get(
        f"/api/job-matching/matches/{match_id}/apply-redirect",
        headers=headers,
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == seeded_match["posting"].source_url


async def test_apply_redirect_sets_apply_clicked_at_on_first_click(
    client: TestClient, db: AsyncSession, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_uuid = seeded_match["match"].id
    match_id = str(match_uuid)

    client.get(
        f"/api/job-matching/matches/{match_id}/apply-redirect",
        headers=headers,
        follow_redirects=False,
    )

    db.expire_all()
    result = await db.execute(select(JobMatch).where(JobMatch.id == match_uuid))
    match = result.scalar_one()
    assert match.apply_clicked_at is not None


async def test_apply_redirect_is_idempotent_across_repeated_clicks(
    client: TestClient, db: AsyncSession, seeded_match: dict[str, Any]
) -> None:
    """apply_clicked_at is set on the first click and unchanged on a second click."""
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_uuid = seeded_match["match"].id
    match_id = str(match_uuid)

    client.get(
        f"/api/job-matching/matches/{match_id}/apply-redirect",
        headers=headers,
        follow_redirects=False,
    )
    db.expire_all()
    result = await db.execute(select(JobMatch).where(JobMatch.id == match_uuid))
    first_clicked_at = result.scalar_one().apply_clicked_at
    assert first_clicked_at is not None

    client.get(
        f"/api/job-matching/matches/{match_id}/apply-redirect",
        headers=headers,
        follow_redirects=False,
    )
    db.expire_all()
    result = await db.execute(select(JobMatch).where(JobMatch.id == match_uuid))
    second_clicked_at = result.scalar_one().apply_clicked_at
    assert second_clicked_at == first_clicked_at


def test_apply_redirect_other_users_match_returns_404(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    other_user_headers = _auth_headers()  # different (fresh) user id
    match_id = str(seeded_match["match"].id)

    response = client.get(
        f"/api/job-matching/matches/{match_id}/apply-redirect",
        headers=other_user_headers,
        follow_redirects=False,
    )
    assert_error(response, 404, "NOT_FOUND")


def test_apply_redirect_bogus_match_id_returns_404(client: TestClient) -> None:
    headers = _auth_headers()
    bogus_id = str(uuid4())

    response = client.get(
        f"/api/job-matching/matches/{bogus_id}/apply-redirect",
        headers=headers,
        follow_redirects=False,
    )
    assert_error(response, 404, "NOT_FOUND")


def test_apply_redirect_posting_without_source_url_returns_404(
    client: TestClient, seeded_match_without_source_url: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match_without_source_url["user_id"]))
    match_id = str(seeded_match_without_source_url["match"].id)

    response = client.get(
        f"/api/job-matching/matches/{match_id}/apply-redirect",
        headers=headers,
        follow_redirects=False,
    )
    assert_error(response, 404, "NOT_FOUND")


def test_mark_applied_true_sets_applied_at(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    response = client.post(
        f"/api/job-matching/matches/{match_id}/mark-applied",
        headers=headers,
        json={"applied": True},
    )
    assert response.status_code == 204

    fetched = client.get("/api/job-matching/matches", headers=headers)
    data = assert_success(fetched)
    assert data["matches"][0]["applied_at"] is not None


def test_mark_applied_toggles_back_to_unapplied(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    match_id = str(seeded_match["match"].id)

    client.post(
        f"/api/job-matching/matches/{match_id}/mark-applied",
        headers=headers,
        json={"applied": True},
    )
    response = client.post(
        f"/api/job-matching/matches/{match_id}/mark-applied",
        headers=headers,
        json={"applied": False},
    )
    assert response.status_code == 204

    fetched = client.get("/api/job-matching/matches", headers=headers)
    data = assert_success(fetched)
    assert data["matches"][0]["applied_at"] is None


def test_mark_applied_other_users_match_returns_404(
    client: TestClient, seeded_match: dict[str, Any]
) -> None:
    other_user_headers = _auth_headers()  # different (fresh) user id
    match_id = str(seeded_match["match"].id)

    response = client.post(
        f"/api/job-matching/matches/{match_id}/mark-applied",
        headers=other_user_headers,
        json={"applied": True},
    )
    assert_error(response, 404, "NOT_FOUND")


def test_mark_applied_bogus_match_id_returns_404(client: TestClient) -> None:
    headers = _auth_headers()
    bogus_id = str(uuid4())

    response = client.post(
        f"/api/job-matching/matches/{bogus_id}/mark-applied",
        headers=headers,
        json={"applied": True},
    )
    assert_error(response, 404, "NOT_FOUND")


# ---------------------------------------------------------------------------
# GET /api/job-matching/events
# ---------------------------------------------------------------------------


class _FastFailPubSub:
    """Pub/sub stub whose `get_message` raises immediately, forcing the route's
    subscribe/wait loop to exit right after the initial-count event.

    Without this, the route calls `events.stream_unread_match_events(...)` with no
    custom `heartbeat_seconds`/`max_seconds` args, so it falls back to the module's
    real defaults (15s heartbeat, 300s max). Monkeypatching the `HEARTBEAT_SECONDS`/
    `MAX_STREAM_SECONDS` module constants would NOT help here: they're bound as
    function *default argument values* at module-import time, so rebinding the
    module attribute after import doesn't change the already-bound defaults on
    `stream_unread_match_events`. Monkeypatching the Redis client itself to fail
    fast avoids that trap entirely and exercises the source's own
    `except RedisError: return` early-exit branch.
    """

    async def subscribe(self, channel: str) -> None:
        return None

    async def get_message(
        self, *, timeout: float, ignore_subscribe_messages: bool = True
    ) -> dict[str, str] | None:
        raise RedisError("stubbed for test speed")

    async def unsubscribe(self, channel: str) -> None:
        return None

    async def aclose(self) -> None:
        return None


class _FastFailEventsRedis:
    def pubsub(self) -> _FastFailPubSub:
        return _FastFailPubSub()


@pytest.fixture
def fast_events_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        job_matching_events, "_get_events_redis_client", lambda: _FastFailEventsRedis()
    )


def test_events_route_returns_sse_stream_with_initial_count(
    client: TestClient, fast_events_redis: None
) -> None:
    response = client.get("/api/job-matching/events", headers=_auth_headers())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.splitlines()[0] == 'data: {"unread_count": 0}'


def test_events_route_initial_count_reflects_unread_matches(
    client: TestClient, seeded_match: dict[str, Any], fast_events_redis: None
) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))

    response = client.get("/api/job-matching/events", headers=headers)

    assert response.status_code == 200
    # seeded_match's JobMatch has viewed_at=None (unviewed) -> counted as unread.
    assert response.text.splitlines()[0] == 'data: {"unread_count": 1}'


# ---------------------------------------------------------------------------
# POST /api/job-matching/scan
# ---------------------------------------------------------------------------


def test_trigger_scan_returns_enqueued(client: TestClient) -> None:
    """RQ's Queue talks to Redis directly, which isn't available in CI (RULE.md: no
    live external calls in CI), so the Queue class used inside the service module is
    patched directly here rather than relying on a real/fake connection.
    """
    with patch("app.modules.job_matching.service.Queue") as mock_queue_cls:
        mock_queue_cls.return_value.enqueue = MagicMock(return_value=None)
        response = client.post("/api/job-matching/scan", headers=_auth_headers())

    data = assert_success(response)
    assert data["scan_enqueued"] is True
    assert isinstance(data["message"], str) and data["message"]
    mock_queue_cls.return_value.enqueue.assert_called_once()


# ---------------------------------------------------------------------------
# POST/DELETE /api/job-matching/push-subscription
# ---------------------------------------------------------------------------


async def _get_subscription_by_endpoint(db: AsyncSession, endpoint: str) -> PushSubscription | None:
    result = await db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    return result.scalar_one_or_none()


def test_create_push_subscription_success(client: TestClient, db: AsyncSession) -> None:
    user_id = str(uuid4())
    headers = _auth_headers(user_id)
    endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid4().hex}"

    response = client.post(
        "/api/job-matching/push-subscription",
        headers=headers,
        json={"endpoint": endpoint, "p256dh": "fake-p256dh", "auth": "fake-auth"},
    )
    assert response.status_code == 204


async def test_create_push_subscription_persists_row(client: TestClient, db: AsyncSession) -> None:
    user_id = str(uuid4())
    headers = _auth_headers(user_id)
    endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid4().hex}"

    client.post(
        "/api/job-matching/push-subscription",
        headers=headers,
        json={"endpoint": endpoint, "p256dh": "fake-p256dh", "auth": "fake-auth"},
    )

    subscription = await _get_subscription_by_endpoint(db, endpoint)
    assert subscription is not None
    assert str(subscription.user_id) == user_id
    assert subscription.p256dh_key == "fake-p256dh"
    assert subscription.auth_key == "fake-auth"


async def test_create_push_subscription_upserts_by_endpoint(
    client: TestClient, db: AsyncSession
) -> None:
    """Re-subscribing with the same endpoint (e.g. browser re-registering) updates the
    existing row's keys/user_id rather than creating a duplicate."""
    endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid4().hex}"
    first_user_id = str(uuid4())
    second_user_id = str(uuid4())

    client.post(
        "/api/job-matching/push-subscription",
        headers=_auth_headers(first_user_id),
        json={"endpoint": endpoint, "p256dh": "old-p256dh", "auth": "old-auth"},
    )
    response = client.post(
        "/api/job-matching/push-subscription",
        headers=_auth_headers(second_user_id),
        json={"endpoint": endpoint, "p256dh": "new-p256dh", "auth": "new-auth"},
    )
    assert response.status_code == 204

    subscription = await _get_subscription_by_endpoint(db, endpoint)
    assert subscription is not None
    assert str(subscription.user_id) == second_user_id
    assert subscription.p256dh_key == "new-p256dh"
    assert subscription.auth_key == "new-auth"


def test_create_push_subscription_missing_fields_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/job-matching/push-subscription",
        headers=_auth_headers(),
        json={"endpoint": "https://fcm.googleapis.com/fcm/send/abc"},
    )
    assert response.status_code == 422


async def test_delete_push_subscription_success(client: TestClient, db: AsyncSession) -> None:
    user_id = str(uuid4())
    headers = _auth_headers(user_id)
    endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid4().hex}"
    client.post(
        "/api/job-matching/push-subscription",
        headers=headers,
        json={"endpoint": endpoint, "p256dh": "fake-p256dh", "auth": "fake-auth"},
    )

    response = client.request(
        "DELETE",
        "/api/job-matching/push-subscription",
        headers=headers,
        json={"endpoint": endpoint},
    )
    assert response.status_code == 204

    subscription = await _get_subscription_by_endpoint(db, endpoint)
    assert subscription is None


async def test_delete_push_subscription_scoped_to_user(
    client: TestClient, db: AsyncSession
) -> None:
    """A user can't delete another user's push subscription."""
    owner_id = str(uuid4())
    other_id = str(uuid4())
    endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid4().hex}"
    client.post(
        "/api/job-matching/push-subscription",
        headers=_auth_headers(owner_id),
        json={"endpoint": endpoint, "p256dh": "fake-p256dh", "auth": "fake-auth"},
    )

    response = client.request(
        "DELETE",
        "/api/job-matching/push-subscription",
        headers=_auth_headers(other_id),
        json={"endpoint": endpoint},
    )
    assert response.status_code == 204

    subscription = await _get_subscription_by_endpoint(db, endpoint)
    assert subscription is not None
    assert str(subscription.user_id) == owner_id


def test_delete_push_subscription_bogus_endpoint_is_noop(client: TestClient) -> None:
    """Deleting a non-existent subscription is a no-op, not an error."""
    response = client.request(
        "DELETE",
        "/api/job-matching/push-subscription",
        headers=_auth_headers(),
        json={"endpoint": "https://fcm.googleapis.com/fcm/send/does-not-exist"},
    )
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Auth requirements (all endpoints)
# ---------------------------------------------------------------------------

_UNAUTHENTICATED_REQUESTS = [
    ("GET", "/api/job-matching/preferences", None),
    ("PUT", "/api/job-matching/preferences", {"desired_roles": []}),
    ("GET", "/api/job-matching/matches", None),
    ("POST", f"/api/job-matching/matches/{uuid4()}/view", None),
    ("POST", f"/api/job-matching/matches/{uuid4()}/feedback", {"feedback": "up"}),
    ("GET", f"/api/job-matching/matches/{uuid4()}/apply-redirect", None),
    ("POST", f"/api/job-matching/matches/{uuid4()}/mark-applied", {"applied": True}),
    ("POST", "/api/job-matching/scan", None),
    ("GET", "/api/job-matching/events", None),
    (
        "POST",
        "/api/job-matching/push-subscription",
        {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "p256dh": "x", "auth": "y"},
    ),
    (
        "DELETE",
        "/api/job-matching/push-subscription",
        {"endpoint": "https://fcm.googleapis.com/fcm/send/abc"},
    ),
]


@pytest.mark.parametrize("method,path,body", _UNAUTHENTICATED_REQUESTS)
def test_endpoints_require_auth(
    client: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = client.request(method, path, json=body)
    body_json = assert_error(response, 401, "UNAUTHORIZED")
    # Job matching's auth dependency (test_auth_dependency, via require_verified_user /
    # get_current_user_from_cookie overrides) raises this detail message when the
    # Authorization header is missing -- distinct from the legacy verify_token
    # dependency's "unauthorized" message used elsewhere (e.g. /api/signals).
    assert body_json["error"]["message"] == "Invalid or missing authorization"
