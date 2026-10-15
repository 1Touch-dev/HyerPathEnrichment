"""Google OAuth unit tests — state, userinfo exchange, and upsert behavior."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google_oauth import (
    exchange_google_code,
    fetch_google_userinfo,
    make_oauth_state,
    upsert_google_user,
    verify_oauth_state,
)
from app.auth.models import OAuthAccount, User
from app.auth.password import hash_password
from app.core.config import Settings
from app.main import app


def _settings(**overrides: Any) -> Settings:
    base = {
        "GOOGLE_OAUTH_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
        "GOOGLE_OAUTH_REDIRECT_URL": "https://app.hyerpath.com/callback/google",
        "SECRET_KEY": "unit-test-secret-key-not-for-prod",
    }
    base.update(overrides)
    return Settings(**base)


def test_oauth_state_roundtrip() -> None:
    secret = "unit-test-secret-key-not-for-prod"
    state = make_oauth_state(secret)
    assert verify_oauth_state(secret, state) is True


def test_oauth_state_rejects_tampered_and_missing() -> None:
    secret = "unit-test-secret-key-not-for-prod"
    state = make_oauth_state(secret)
    assert verify_oauth_state(secret, None) is False
    assert verify_oauth_state(secret, "not-a-state") is False
    assert verify_oauth_state(secret, state + "x") is False
    assert verify_oauth_state("other-secret", state) is False


def test_oauth_state_rejects_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "unit-test-secret-key-not-for-prod"
    now = 1_700_000_000
    monkeypatch.setattr("app.auth.google_oauth.time.time", lambda: now)
    state = make_oauth_state(secret)
    monkeypatch.setattr("app.auth.google_oauth.time.time", lambda: now + 601)
    assert verify_oauth_state(secret, state) is False


@pytest.mark.asyncio
async def test_fetch_google_userinfo_success() -> None:
    payload = {
        "sub": "google-sub-1",
        "email": "user@example.com",
        "email_verified": True,
        "given_name": "Ada",
        "family_name": "Lovelace",
        "picture": "https://example.com/a.png",
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.auth.google_oauth.httpx.AsyncClient", return_value=mock_client):
        profile = await fetch_google_userinfo("access-token")

    assert profile["sub"] == "google-sub-1"
    mock_client.get.assert_awaited_once()
    args, kwargs = mock_client.get.await_args
    assert args[0] == "https://openidconnect.googleapis.com/v1/userinfo"
    assert kwargs["headers"]["Authorization"] == "Bearer access-token"


@pytest.mark.asyncio
async def test_fetch_google_userinfo_http_error() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"error": "forbidden"}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.auth.google_oauth.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="Google userinfo failed"):
            await fetch_google_userinfo("access-token")


@pytest.mark.asyncio
async def test_exchange_google_code_uses_userinfo_not_people_api() -> None:
    settings = _settings()
    token_payload = {
        "access_token": "ya29.access",
        "refresh_token": None,
        "expires_at": 1_700_000_100,
    }
    userinfo = {
        "sub": "1122334455",
        "email": "newbie@example.com",
        "email_verified": True,
        "given_name": "New",
        "family_name": "User",
        "picture": "https://example.com/p.png",
    }

    mock_oauth = AsyncMock()
    mock_oauth.get_access_token.return_value = token_payload

    with (
        patch("app.auth.google_oauth._google_client", return_value=mock_oauth),
        patch(
            "app.auth.google_oauth.fetch_google_userinfo",
            AsyncMock(return_value=userinfo),
        ) as mock_userinfo,
    ):
        google_id, email, profile, access, refresh, expires = await exchange_google_code(
            settings, code="auth-code"
        )

    mock_oauth.get_access_token.assert_awaited_once_with(
        "auth-code", "https://app.hyerpath.com/callback/google"
    )
    mock_userinfo.assert_awaited_once_with("ya29.access")
    assert google_id == "1122334455"
    assert email == "newbie@example.com"
    assert profile["given_name"] == "New"
    assert access == "ya29.access"
    assert refresh is None
    assert expires == 1_700_000_100


@pytest.mark.asyncio
async def test_exchange_google_code_rejects_unverified_email() -> None:
    settings = _settings()
    mock_oauth = AsyncMock()
    mock_oauth.get_access_token.return_value = {"access_token": "tok"}

    with (
        patch("app.auth.google_oauth._google_client", return_value=mock_oauth),
        patch(
            "app.auth.google_oauth.fetch_google_userinfo",
            AsyncMock(
                return_value={
                    "sub": "1",
                    "email": "u@example.com",
                    "email_verified": False,
                }
            ),
        ),
    ):
        with pytest.raises(ValueError, match="not verified"):
            await exchange_google_code(settings, code="auth-code")


@pytest.mark.asyncio
async def test_upsert_creates_new_google_user(db: AsyncSession) -> None:
    user = await upsert_google_user(
        db,
        google_id="g-new-1",
        email="Brand.New@Example.com",
        access_token="atok",
        refresh_token=None,
        expires_at=None,
        profile={"given_name": "Brand", "family_name": "New", "picture": "https://x/y.png"},
    )
    assert user.email == "brand.new@example.com"
    assert user.oauth_provider == "google"
    assert user.oauth_id == "g-new-1"
    assert user.is_verified is True
    assert user.hashed_password is None

    oauth = (
        await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.oauth_name == "google", OAuthAccount.account_id == "g-new-1"
            )
        )
    ).scalar_one()
    assert oauth.user_id == user.id
    assert oauth.account_email == "brand.new@example.com"


@pytest.mark.asyncio
async def test_upsert_existing_google_user_no_duplicate(db: AsyncSession) -> None:
    first = await upsert_google_user(
        db,
        google_id="g-exist-1",
        email="exist@example.com",
        access_token="atok1",
        refresh_token=None,
        expires_at=None,
        profile={"given_name": "Ex", "family_name": "Ist"},
    )
    second = await upsert_google_user(
        db,
        google_id="g-exist-1",
        email="exist@example.com",
        access_token="atok2",
        refresh_token=None,
        expires_at=None,
        profile={"given_name": "Ex", "family_name": "Ist"},
    )
    assert second.id == first.id
    count = (
        (await db.execute(select(OAuthAccount).where(OAuthAccount.account_id == "g-exist-1")))
        .scalars()
        .all()
    )
    assert len(count) == 1


@pytest.mark.asyncio
async def test_upsert_links_existing_password_account(db: AsyncSession) -> None:
    existing = User(
        email="linked@example.com",
        hashed_password=hash_password("SecurePass123!"),
        first_name="Pass",
        last_name="User",
        is_verified=False,
        is_active=True,
    )
    db.add(existing)
    await db.commit()
    await db.refresh(existing)

    linked = await upsert_google_user(
        db,
        google_id="g-link-1",
        email="linked@example.com",
        access_token="atok",
        refresh_token=None,
        expires_at=None,
        profile={"given_name": "Pass", "family_name": "User"},
    )
    assert linked.id == existing.id
    assert linked.is_verified is True
    assert linked.oauth_provider == "google"
    assert linked.hashed_password is not None  # password login remains possible


@pytest.mark.asyncio
async def test_google_callback_rejects_invalid_state(db: AsyncSession) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch(
            "app.auth.router.oauth_configured",
            return_value=True,
        ):
            response = await client.get(
                "/auth/google/callback",
                params={"code": "abc", "state": "invalid"},
            )
    assert response.status_code == 400
    body = response.json()
    detail = body.get("detail") or body.get("error", {}).get("message")
    assert "state" in str(detail).lower()


@pytest.mark.asyncio
async def test_google_callback_rejects_provider_error(db: AsyncSession) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.auth.router.oauth_configured", return_value=True):
            response = await client.get(
                "/auth/google/callback",
                params={"error": "access_denied"},
            )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_google_callback_success_sets_cookies(db: AsyncSession) -> None:
    fake_user = User(
        email="oauth-ok@example.com",
        hashed_password=None,
        first_name="O",
        last_name="Auth",
        is_verified=True,
        is_active=True,
        oauth_provider="google",
        oauth_id="g-ok-1",
    )
    db.add(fake_user)
    await db.commit()
    await db.refresh(fake_user)

    settings = _settings()
    state = make_oauth_state(settings.SECRET_KEY)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("app.auth.router.oauth_configured", return_value=True),
            patch("app.auth.router.get_settings", return_value=settings),
            patch(
                "app.auth.router.exchange_google_code",
                AsyncMock(
                    return_value=(
                        "g-ok-1",
                        "oauth-ok@example.com",
                        {"sub": "g-ok-1", "email": "oauth-ok@example.com"},
                        "atok",
                        None,
                        None,
                    )
                ),
            ),
            patch(
                "app.auth.router.upsert_google_user",
                AsyncMock(return_value=fake_user),
            ),
        ):
            response = await client.get(
                "/auth/google/callback",
                params={"code": "good-code", "state": state},
            )

    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_google_callback_maps_exchange_failure_to_400(db: AsyncSession) -> None:
    settings = _settings()
    state = make_oauth_state(settings.SECRET_KEY)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("app.auth.router.oauth_configured", return_value=True),
            patch("app.auth.router.get_settings", return_value=settings),
            patch(
                "app.auth.router.exchange_google_code",
                AsyncMock(side_effect=httpx.HTTPError("token exchange failed")),
            ),
        ):
            response = await client.get(
                "/auth/google/callback",
                params={"code": "bad-code", "state": state},
            )

    assert response.status_code == 400
    body = response.json()
    detail = body.get("detail") or body.get("error", {}).get("message")
    assert "Google OAuth login failed" in str(detail)
