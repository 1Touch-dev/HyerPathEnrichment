"""Tests for validate_billing_settings()."""

from __future__ import annotations

import pytest

from app.core.config import Settings, validate_billing_settings


def test_no_op_when_billing_disabled() -> None:
    validate_billing_settings(
        Settings(
            ENABLE_BILLING=False,
            STRIPE_SECRET_KEY="",
            STRIPE_WEBHOOK_SECRET="",
            STRIPE_PRICE_ID_PREMIUM="",
        )
    )


def test_raises_when_enabled_without_keys() -> None:
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
        validate_billing_settings(
            Settings(
                ENABLE_BILLING=True,
                STRIPE_SECRET_KEY="",
                STRIPE_WEBHOOK_SECRET="whsec_test",
                STRIPE_PRICE_ID_PREMIUM="price_test",
            )
        )


def test_passes_when_enabled_with_all_keys() -> None:
    validate_billing_settings(
        Settings(
            ENABLE_BILLING=True,
            STRIPE_SECRET_KEY="sk_test_x",
            STRIPE_WEBHOOK_SECRET="whsec_test",
            STRIPE_PRICE_ID_PREMIUM="price_test",
        )
    )


def test_mock_keys_pass_in_development() -> None:
    validate_billing_settings(
        Settings(
            ENABLE_BILLING=True,
            APP_ENV="development",
            STRIPE_MODE="mock",
            STRIPE_SECRET_KEY="sk_test_mock",
            STRIPE_WEBHOOK_SECRET="whsec_test_local_secret",
            STRIPE_PRICE_ID_PREMIUM="price_mock_premium",
        )
    )


def test_mock_rejected_in_staging() -> None:
    with pytest.raises(RuntimeError, match="STRIPE_MODE"):
        validate_billing_settings(
            Settings(
                ENABLE_BILLING=True,
                APP_ENV="staging",
                STRIPE_MODE="mock",
                STRIPE_SECRET_KEY="sk_test_mock",
                STRIPE_WEBHOOK_SECRET="whsec_test_local_secret",
                STRIPE_PRICE_ID_PREMIUM="price_mock_premium",
            )
        )


def test_mock_rejected_in_production() -> None:
    with pytest.raises(RuntimeError, match="STRIPE_MODE"):
        validate_billing_settings(
            Settings(
                ENABLE_BILLING=True,
                APP_ENV="production",
                STRIPE_MODE="mock",
                STRIPE_SECRET_KEY="sk_test_mock",
                STRIPE_WEBHOOK_SECRET="whsec_test_local_secret",
                STRIPE_PRICE_ID_PREMIUM="price_mock_premium",
            )
        )


def test_live_requires_all_three_keys() -> None:
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
        validate_billing_settings(
            Settings(
                ENABLE_BILLING=True,
                STRIPE_MODE="live",
                STRIPE_SECRET_KEY="",
                STRIPE_WEBHOOK_SECRET="",
                STRIPE_PRICE_ID_PREMIUM="",
            )
        )
