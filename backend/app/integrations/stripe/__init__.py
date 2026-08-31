"""Thin Stripe SDK wrapper for billing (checkout, portal, webhooks)."""

from __future__ import annotations

from app.integrations.stripe.client import StripeClient

__all__ = ["StripeClient"]
