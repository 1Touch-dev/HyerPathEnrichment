from __future__ import annotations

import asyncio

from scripts.create_test_user import validate_bootstrap_context
from scripts import create_test_user


def test_regular_bootstrap_allowed_in_test_env(monkeypatch):
    monkeypatch.delenv("ALLOW_E2E_SUPERUSER_BOOTSTRAP", raising=False)
    validate_bootstrap_context(app_env="test", is_superuser=False)


def test_superuser_bootstrap_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("ALLOW_E2E_SUPERUSER_BOOTSTRAP", raising=False)
    try:
        validate_bootstrap_context(app_env="development", is_superuser=True)
    except RuntimeError as exc:
        assert "ALLOW_E2E_SUPERUSER_BOOTSTRAP" in str(exc)
    else:
        raise AssertionError("superuser bootstrap must require explicit opt-in")


def test_superuser_bootstrap_allowed_with_opt_in(monkeypatch):
    monkeypatch.setenv("ALLOW_E2E_SUPERUSER_BOOTSTRAP", "1")
    validate_bootstrap_context(app_env="development", is_superuser=True)


def test_bootstrap_disallowed_in_production_like_env(monkeypatch):
    monkeypatch.setenv("ALLOW_E2E_SUPERUSER_BOOTSTRAP", "1")
    try:
        validate_bootstrap_context(app_env="production", is_superuser=False)
    except RuntimeError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("bootstrap must be disabled in production-like envs")


def test_schema_is_initialized_before_user_write(monkeypatch):
    calls: list[object] = []

    async def fake_init_db() -> None:
        calls.append("init_db")

    async def fake_create_or_update_user(
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        *,
        is_superuser: bool = False,
    ) -> None:
        calls.append(
            {
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "is_superuser": is_superuser,
            }
        )

    monkeypatch.setattr(create_test_user, "_create_or_update_user", fake_create_or_update_user)

    asyncio.run(
        create_test_user._ensure_schema_and_create_user(
            "fixture@example.com",
            "FixturePassword123",
            "Fixture",
            "User",
            is_superuser=True,
            init_db_func=fake_init_db,
        )
    )

    assert calls == [
        "init_db",
        {
            "email": "fixture@example.com",
            "password": "FixturePassword123",
            "first_name": "Fixture",
            "last_name": "User",
            "is_superuser": True,
        },
    ]
