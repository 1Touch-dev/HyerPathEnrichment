"""Tests for Tier 1 startup settings validation."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.core.config import Settings, validate_tier1_settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "enable_tier1": False,
        "browser_mode": "local",
        "app_env": "development",
        "multilogin_email": "",
        "multilogin_password": SecretStr(""),
        "multilogin_folder_id": "",
        "linkedin_bot_email": "",
        "linkedin_bot_password": SecretStr(""),
        "r2_account_id": "",
        "r2_access_key_id": "",
        "r2_secret_access_key": SecretStr(""),
        "r2_bucket": "hyrepath-assets",
    }
    base.update(overrides)
    # Bypass env/.env so local credentials cannot mask missing-key cases.
    return Settings.model_construct(**base)


def _complete_multilogin(**overrides: object) -> Settings:
    return _settings(
        enable_tier1=True,
        browser_mode="multilogin",
        multilogin_email="bot@example.com",
        multilogin_password=SecretStr("secret"),
        multilogin_folder_id="folder-uuid",
        linkedin_bot_email="li@example.com",
        linkedin_bot_password=SecretStr("li-secret"),
        **overrides,
    )


def test_tier1_off_does_not_raise() -> None:
    validate_tier1_settings(_settings(enable_tier1=False))


def test_tier1_multilogin_missing_email_and_folder_raises() -> None:
    settings = _settings(
        enable_tier1=True,
        browser_mode="multilogin",
        multilogin_password=SecretStr("secret"),
        linkedin_bot_email="li@example.com",
        linkedin_bot_password=SecretStr("li-secret"),
    )
    with pytest.raises(RuntimeError, match="MULTILOGIN_EMAIL") as exc_info:
        validate_tier1_settings(settings)
    message = str(exc_info.value)
    assert "MULTILOGIN_FOLDER_ID" in message
    assert "secret" not in message


def test_tier1_multilogin_complete_ok() -> None:
    validate_tier1_settings(_complete_multilogin())


def test_tier1_production_without_r2_raises() -> None:
    settings = _complete_multilogin(app_env="production")
    with pytest.raises(RuntimeError, match="R2_ACCOUNT_ID"):
        validate_tier1_settings(settings)


def test_tier1_development_without_r2_ok() -> None:
    validate_tier1_settings(_complete_multilogin(app_env="development"))
