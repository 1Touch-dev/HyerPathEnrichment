from __future__ import annotations

from scripts.create_test_user import validate_bootstrap_context


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
