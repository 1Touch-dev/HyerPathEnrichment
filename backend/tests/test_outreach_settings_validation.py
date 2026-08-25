"""Tests for outreach startup settings validation (machine-2/05, CAN-SPAM)."""

from __future__ import annotations

import pytest

from app.core.config import Settings, validate_outreach_settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "outreach_enabled": False,
        "outreach_physical_address": "",
    }
    base.update(overrides)
    # Bypass env/.env so local defaults cannot mask missing-key cases.
    return Settings.model_construct(**base)


def test_outreach_disabled_does_not_raise_even_without_address() -> None:
    validate_outreach_settings(_settings(outreach_enabled=False, outreach_physical_address=""))


def test_outreach_enabled_missing_physical_address_raises() -> None:
    settings = _settings(outreach_enabled=True, outreach_physical_address="")
    with pytest.raises(RuntimeError, match="OUTREACH_PHYSICAL_ADDRESS"):
        validate_outreach_settings(settings)


def test_outreach_enabled_blank_physical_address_raises() -> None:
    settings = _settings(outreach_enabled=True, outreach_physical_address="   ")
    with pytest.raises(RuntimeError, match="OUTREACH_PHYSICAL_ADDRESS"):
        validate_outreach_settings(settings)


def test_outreach_enabled_with_physical_address_ok() -> None:
    settings = _settings(
        outreach_enabled=True, outreach_physical_address="123 Main St, San Francisco, CA"
    )
    validate_outreach_settings(settings)
