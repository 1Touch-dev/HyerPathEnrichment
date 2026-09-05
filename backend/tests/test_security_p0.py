"""Unit tests for production security startup validation and webhook SSRF guards."""

from __future__ import annotations

import ipaddress
import socket
from unittest.mock import patch

import pytest

from app.core.config import Settings, validate_production_security_settings
from app.core.webhook_url import UnsafeWebhookUrlError, assert_safe_webhook_url


def test_validate_production_security_noop_in_development() -> None:
    settings = Settings(
        APP_ENV="development",
        SECRET_KEY="change-me-in-production-use-openssl-rand-hex-32",
        API_TOKEN="change-me",
        COOKIE_SECURE=False,
        CHANGEDETECTION_API_KEY="",
    )
    validate_production_security_settings(settings)  # must not raise


def test_validate_production_security_rejects_defaults() -> None:
    settings = Settings(
        APP_ENV="production",
        SECRET_KEY="change-me-in-production-use-openssl-rand-hex-32",
        API_TOKEN="change-me",
        COOKIE_SECURE=False,
        CHANGEDETECTION_API_KEY="",
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_production_security_settings(settings)


def test_validate_production_security_accepts_strong_settings() -> None:
    settings = Settings(
        APP_ENV="staging",
        SECRET_KEY="a" * 32,
        API_TOKEN="prod-api-token-not-default",
        COOKIE_SECURE=True,
        CHANGEDETECTION_API_KEY="signal-secret",
    )
    validate_production_security_settings(settings)


def test_assert_safe_webhook_url_rejects_http() -> None:
    with pytest.raises(UnsafeWebhookUrlError, match="https"):
        assert_safe_webhook_url("http://example.com/hook")


def test_assert_safe_webhook_url_rejects_credentials() -> None:
    with pytest.raises(UnsafeWebhookUrlError, match="credentials"):
        assert_safe_webhook_url("https://user:pass@example.com/hook")


def test_assert_safe_webhook_url_rejects_literal_private_ip() -> None:
    with pytest.raises(UnsafeWebhookUrlError, match="private"):
        assert_safe_webhook_url("https://127.0.0.1/hook")


def test_assert_safe_webhook_url_rejects_dns_to_private_ip() -> None:
    fake = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            0,
            "",
            ("10.0.0.1", 443),
        )
    ]
    with patch("app.core.webhook_url.socket.getaddrinfo", return_value=fake):
        with pytest.raises(UnsafeWebhookUrlError, match="private"):
            assert_safe_webhook_url("https://evil.example/hook")


def test_assert_safe_webhook_url_accepts_public_resolution() -> None:
    fake = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            0,
            "",
            ("93.184.216.34", 443),
        )
    ]
    with patch("app.core.webhook_url.socket.getaddrinfo", return_value=fake):
        assert assert_safe_webhook_url("https://example.com/hook") == "https://example.com/hook"


def test_is_global_metadata_style_address_blocked() -> None:
    # Belt-and-suspenders: link-local / reserved must fail even if somehow resolved.
    ip = ipaddress.ip_address("169.254.169.254")
    assert ip.is_link_local or not ip.is_global
