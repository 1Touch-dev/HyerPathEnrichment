"""Tests for app.modules.job_matching.push: subscribe/unsubscribe upsert semantics
and fail-soft send_push_notification behavior.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from pywebpush import WebPushException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.modules.job_matching import push
from app.modules.job_matching.models import PushSubscription


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        email=f"push-primary-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Push",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def other_user(db: AsyncSession) -> User:
    user = User(
        email=f"push-other-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _get_subscription_by_endpoint(db: AsyncSession, endpoint: str) -> PushSubscription | None:
    result = await db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    return result.scalar_one_or_none()


class TestSubscribe:
    async def test_creates_new_subscription(self, db: AsyncSession, test_user: User) -> None:
        endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"

        await push.subscribe(db, test_user.id, endpoint, "p256dh-key", "auth-key")

        row = await _get_subscription_by_endpoint(db, endpoint)
        assert row is not None
        assert row.user_id == test_user.id
        assert row.p256dh_key == "p256dh-key"
        assert row.auth_key == "auth-key"

    async def test_upserts_by_endpoint_when_already_exists(
        self, db: AsyncSession, test_user: User, other_user: User
    ) -> None:
        """Re-subscribing with the same endpoint (e.g. a shared device where a
        different user later logs in) updates the existing row rather than creating
        a duplicate."""
        endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"

        await push.subscribe(db, test_user.id, endpoint, "old-p256dh", "old-auth")
        await push.subscribe(db, other_user.id, endpoint, "new-p256dh", "new-auth")

        result = await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].user_id == other_user.id
        assert rows[0].p256dh_key == "new-p256dh"
        assert rows[0].auth_key == "new-auth"

    async def test_upsert_sets_last_used_at(self, db: AsyncSession, test_user: User) -> None:
        endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"

        await push.subscribe(db, test_user.id, endpoint, "p256dh-key", "auth-key")
        await push.subscribe(db, test_user.id, endpoint, "p256dh-key", "auth-key")

        row = await _get_subscription_by_endpoint(db, endpoint)
        assert row is not None
        assert row.last_used_at is not None


class TestUnsubscribe:
    async def test_deletes_matching_subscription(self, db: AsyncSession, test_user: User) -> None:
        endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"
        await push.subscribe(db, test_user.id, endpoint, "p256dh-key", "auth-key")

        await push.unsubscribe(db, test_user.id, endpoint)

        row = await _get_subscription_by_endpoint(db, endpoint)
        assert row is None

    async def test_cannot_delete_another_users_subscription(
        self, db: AsyncSession, test_user: User, other_user: User
    ) -> None:
        """Scoping by both user_id and endpoint means one user can't delete another
        user's subscription, even if they know the exact endpoint string."""
        endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"
        await push.subscribe(db, test_user.id, endpoint, "p256dh-key", "auth-key")

        await push.unsubscribe(db, other_user.id, endpoint)

        row = await _get_subscription_by_endpoint(db, endpoint)
        assert row is not None
        assert row.user_id == test_user.id

    async def test_unsubscribe_missing_endpoint_is_a_noop(
        self, db: AsyncSession, test_user: User
    ) -> None:
        await push.unsubscribe(db, test_user.id, "https://fcm.googleapis.com/fcm/send/missing")


class TestSendPushNotification:
    async def test_returns_true_on_success(self, db: AsyncSession, test_user: User) -> None:
        endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"
        await push.subscribe(db, test_user.id, endpoint, "p256dh-key", "auth-key")
        subscription = await _get_subscription_by_endpoint(db, endpoint)
        assert subscription is not None

        with patch("app.modules.job_matching.push.webpush", return_value=None) as mock_webpush:
            result = await push.send_push_notification(subscription, {"title": "New match"})

        assert result is True
        mock_webpush.assert_called_once()
        _, kwargs = mock_webpush.call_args
        assert kwargs["subscription_info"]["endpoint"] == endpoint
        assert kwargs["subscription_info"]["keys"]["p256dh"] == "p256dh-key"
        assert kwargs["subscription_info"]["keys"]["auth"] == "auth-key"

    async def test_fail_soft_returns_false_on_webpushexception(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """A WebPushException (e.g. expired/invalid subscription, VAPID misconfig) must
        never propagate out of send_push_notification — mirrors _post_webhook's
        never-raises convention."""
        endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"
        await push.subscribe(db, test_user.id, endpoint, "p256dh-key", "auth-key")
        subscription = await _get_subscription_by_endpoint(db, endpoint)
        assert subscription is not None

        with patch(
            "app.modules.job_matching.push.webpush",
            side_effect=WebPushException("push service rejected the request"),
        ):
            result = await push.send_push_notification(subscription, {"title": "New match"})

        assert result is False
