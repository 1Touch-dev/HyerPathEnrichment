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
