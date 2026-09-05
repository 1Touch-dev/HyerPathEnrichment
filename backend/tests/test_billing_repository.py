"""Repository-layer tests for candidate billing (Stripe), using the shared
test DB fixture. Follows test_job_matching_repository.py's convention: the
real async session fixture is `db` (from conftest.py), and there is no
shared user fixture, so a local `test_user` fixture creates a minimal User
row here -- required because UserSubscription.user_id has a FK to users.id.

Covers every function in app/modules/billing/repository.py:
- get_subscription_for_user (found + not-found)
- get_subscription_by_stripe_customer_id
- create_subscription
- update_subscription (partial-update semantics: only explicitly-passed
  non-None fields change, everything else is left alone)
- event_already_processed (false before / true after mark_event_processed)
- mark_event_processed
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.modules.billing import repository
from app.modules.billing.models import StripeWebhookEvent, UserSubscription


def _assert_same_instant(actual: datetime | None, expected: datetime) -> None:
    """SQLite's DateTime(timezone=True) columns round-trip as naive datetimes
    (tzinfo is dropped), so a direct == against an aware datetime would always
    fail on SQLite even though the stored instant is correct. Compare via
    timestamp() instead, which is agnostic to whether either side is aware."""
    assert actual is not None
    actual_ts = actual.timestamp() if actual.tzinfo else actual.replace(tzinfo=UTC).timestamp()
    assert actual_ts == pytest.approx(expected.timestamp())


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    """Minimal persisted User row -- UserSubscription.user_id has a FK to
    users.id, so subscription rows can't be created without one."""
    user = User(
        email=f"billing-test-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Billing",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestGetSubscriptionForUser:
    async def test_returns_none_when_no_subscription_exists(
        self, db: AsyncSession, test_user: User
    ):
        result = await repository.get_subscription_for_user(db, test_user.id)
        assert result is None

    async def test_returns_the_users_subscription_when_it_exists(
        self, db: AsyncSession, test_user: User
    ):
        created = await repository.create_subscription(
            db,
            user_id=test_user.id,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
        )

        found = await repository.get_subscription_for_user(db, test_user.id)
        assert found is not None
        assert found.id == created.id
        assert found.user_id == test_user.id


class TestGetSubscriptionByStripeCustomerId:
    async def test_returns_none_when_no_match(self, db: AsyncSession):
        result = await repository.get_subscription_by_stripe_customer_id(db, "cus_does_not_exist")
        assert result is None

    async def test_returns_the_matching_subscription(self, db: AsyncSession, test_user: User):
        stripe_customer_id = f"cus_{uuid.uuid4().hex[:12]}"
        created = await repository.create_subscription(
            db, user_id=test_user.id, stripe_customer_id=stripe_customer_id
        )

        found = await repository.get_subscription_by_stripe_customer_id(db, stripe_customer_id)
        assert found is not None
        assert found.id == created.id


class TestCreateSubscription:
    async def test_creates_with_defaults(self, db: AsyncSession, test_user: User):
        stripe_customer_id = f"cus_{uuid.uuid4().hex[:12]}"
        subscription = await repository.create_subscription(
            db, user_id=test_user.id, stripe_customer_id=stripe_customer_id
        )

        assert subscription.id is not None
        assert subscription.user_id == test_user.id
        assert subscription.stripe_customer_id == stripe_customer_id
        assert subscription.stripe_subscription_id is None
        assert subscription.plan_tier == "free"
        assert subscription.status == "active"
        assert subscription.current_period_end is None

        result = await db.execute(
            select(UserSubscription).where(UserSubscription.user_id == test_user.id)
        )
        assert result.scalar_one().id == subscription.id

    async def test_creates_with_all_fields_explicit(self, db: AsyncSession, test_user: User):
        period_end = datetime.now(UTC) + timedelta(days=30)
        subscription = await repository.create_subscription(
            db,
            user_id=test_user.id,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:12]}",
            plan_tier="premium",
            status="trialing",
            current_period_end=period_end,
        )

        assert subscription.plan_tier == "premium"
        assert subscription.status == "trialing"
        assert subscription.stripe_subscription_id is not None
        _assert_same_instant(subscription.current_period_end, period_end)


class TestUpdateSubscription:
    async def test_updates_only_explicitly_passed_non_none_fields(
        self, db: AsyncSession, test_user: User
    ):
        """Partial-update semantics: calling update_subscription with only
        `status` set must leave plan_tier, stripe_subscription_id, and
        current_period_end exactly as they were."""
        original_period_end = datetime.now(UTC) - timedelta(days=1)
        subscription = await repository.create_subscription(
            db,
            user_id=test_user.id,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
            stripe_subscription_id="sub_original",
            plan_tier="premium",
            status="active",
            current_period_end=original_period_end,
        )

        updated = await repository.update_subscription(db, subscription, status="past_due")

        assert updated.status == "past_due"
        # Untouched fields retain their original values.
        assert updated.stripe_subscription_id == "sub_original"
        assert updated.plan_tier == "premium"
        _assert_same_instant(updated.current_period_end, original_period_end)

    async def test_updates_multiple_explicit_fields_together(
        self, db: AsyncSession, test_user: User
    ):
        subscription = await repository.create_subscription(
            db,
            user_id=test_user.id,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
            plan_tier="free",
            status="active",
        )

        new_period_end = datetime.now(UTC) + timedelta(days=30)
        updated = await repository.update_subscription(
            db,
            subscription,
            plan_tier="premium",
            status="active",
            current_period_end=new_period_end,
        )

        assert updated.plan_tier == "premium"
        assert updated.status == "active"
        _assert_same_instant(updated.current_period_end, new_period_end)

    async def test_no_arguments_passed_leaves_all_fields_unchanged(
        self, db: AsyncSession, test_user: User
    ):
        """Calling update_subscription with no explicit fields (all default
        to None) must be a true no-op on the data columns."""
        subscription = await repository.create_subscription(
            db,
            user_id=test_user.id,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
            stripe_subscription_id="sub_untouched",
            plan_tier="premium",
            status="trialing",
        )

        updated = await repository.update_subscription(db, subscription)

        assert updated.stripe_subscription_id == "sub_untouched"
        assert updated.plan_tier == "premium"
        assert updated.status == "trialing"

    async def test_persists_the_update_to_the_database(self, db: AsyncSession, test_user: User):
        subscription = await repository.create_subscription(
            db,
            user_id=test_user.id,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
            plan_tier="free",
            status="active",
        )

        await repository.update_subscription(db, subscription, plan_tier="premium")

        result = await db.execute(
            select(UserSubscription).where(UserSubscription.id == subscription.id)
        )
        refreshed = result.scalar_one()
        assert refreshed.plan_tier == "premium"


class TestEventAlreadyProcessed:
    async def test_returns_false_before_mark_event_processed(self, db: AsyncSession):
        stripe_event_id = f"evt_{uuid.uuid4().hex[:12]}"
        assert await repository.event_already_processed(db, stripe_event_id) is False

    async def test_returns_true_after_mark_event_processed(self, db: AsyncSession):
        stripe_event_id = f"evt_{uuid.uuid4().hex[:12]}"

        await repository.mark_event_processed(db, stripe_event_id, "checkout.session.completed")

        assert await repository.event_already_processed(db, stripe_event_id) is True


class TestMarkEventProcessed:
    async def test_creates_a_stripe_webhook_event_row(self, db: AsyncSession):
        stripe_event_id = f"evt_{uuid.uuid4().hex[:12]}"

        event = await repository.mark_event_processed(
            db, stripe_event_id, "customer.subscription.updated"
        )

        assert event.stripe_event_id == stripe_event_id
        assert event.event_type == "customer.subscription.updated"
        assert event.processed_at is not None

        result = await db.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.stripe_event_id == stripe_event_id)
        )
        assert result.scalar_one().event_type == "customer.subscription.updated"
