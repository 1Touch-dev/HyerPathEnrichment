"""Google OAuth helpers (authorize URL + callback user upsert)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx
from httpx_oauth.clients.google import GoogleOAuth2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import OAuthAccount, User
from app.core.config import Settings

logger = logging.getLogger(__name__)

# OpenID Connect scopes — match Google userinfo, not People API.
GOOGLE_SCOPES = ["openid", "email", "profile"]
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
OAUTH_STATE_MAX_AGE_SECONDS = 600
USERINFO_TIMEOUT_SECONDS = 15.0


def _google_client(settings: Settings) -> GoogleOAuth2:
    return GoogleOAuth2(
        settings.GOOGLE_OAUTH_CLIENT_ID,
        settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value(),
    )


def make_oauth_state(secret: str) -> str:
    """Create a short-lived HMAC state token (CSRF protection)."""
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{ts}.{sig}"


def verify_oauth_state(secret: str, state: str | None) -> bool:
    if not state or "." not in state:
        return False
    ts_str, sig = state.split(".", 1)
    try:
        ts = int(ts_str)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > OAUTH_STATE_MAX_AGE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), ts_str.encode(), hashlib.sha256).hexdigest()[:24]
    return hmac.compare_digest(sig, expected)


async def build_google_authorization_url(settings: Settings) -> tuple[str, str]:
    """Return (authorization_url, state)."""
    client = _google_client(settings)
    state = make_oauth_state(settings.SECRET_KEY)
    url = await client.get_authorization_url(
        redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URL,
        state=state,
        scope=GOOGLE_SCOPES,
        extras_params={"access_type": "online", "prompt": "select_account"},
    )
    return url, state


def _split_name(profile: dict[str, Any], email: str) -> tuple[str, str]:
    given = (profile.get("given_name") or "").strip()
    family = (profile.get("family_name") or "").strip()
    if given or family:
        return given or "Google", family or "User"
    full = (profile.get("name") or "").strip()
    if full:
        parts = full.split(None, 1)
        return parts[0], parts[1] if len(parts) > 1 else "User"
    local = email.split("@", 1)[0] or "Google"
    return local, "User"


async def upsert_google_user(
    db: AsyncSession,
    *,
    google_id: str,
    email: str,
    access_token: str,
    refresh_token: str | None,
    expires_at: int | None,
    profile: dict[str, Any],
) -> User:
    """Find or create a user for a Google account; mark email verified."""
    email_norm = email.strip().lower()
    first_name, last_name = _split_name(profile, email_norm)
    avatar_url = profile.get("picture")

    oauth_row = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.oauth_name == "google",
            OAuthAccount.account_id == google_id,
        )
    )
    existing_oauth = oauth_row.scalar_one_or_none()
    if existing_oauth is not None:
        user = await db.get(User, existing_oauth.user_id)
        if user is None or user.deleted_at is not None:
            raise ValueError("Linked Google account user is missing or deleted")
        existing_oauth.access_token = access_token[:1024]
        existing_oauth.refresh_token = refresh_token[:1024] if refresh_token else None
        existing_oauth.expires_at = expires_at
        existing_oauth.account_email = email_norm
        user.is_verified = True
        user.is_active = True
        if avatar_url and not user.avatar_url:
            user.avatar_url = str(avatar_url)[:1024]
        await db.commit()
        await db.refresh(user)
        return user

    by_email = await db.execute(select(User).where(User.email == email_norm))
    user = by_email.scalar_one_or_none()
    if user is not None and user.deleted_at is not None:
        raise ValueError("This account has been deleted")

    if user is None:
        user = User(
            email=email_norm,
            hashed_password=None,
            first_name=first_name[:100],
            last_name=last_name[:100],
            avatar_url=(str(avatar_url)[:1024] if avatar_url else None),
            oauth_provider="google",
            oauth_id=google_id,
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        await db.flush()
    else:
        # Existing password account with matching verified Google email:
        # link the OAuth identity without overwriting the password hash.
        user.is_verified = True
        user.is_active = True
        if not user.oauth_provider:
            user.oauth_provider = "google"
            user.oauth_id = google_id
        if avatar_url and not user.avatar_url:
            user.avatar_url = str(avatar_url)[:1024]

    db.add(
        OAuthAccount(
            user_id=user.id,
            oauth_name="google",
            access_token=access_token[:1024],
            refresh_token=refresh_token[:1024] if refresh_token else None,
            expires_at=expires_at,
            account_id=google_id,
            account_email=email_norm,
        )
    )
    await db.commit()
    await db.refresh(user)
    return user


async def fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    """
    Fetch OpenID userinfo with the access token.

    httpx_oauth's GoogleOAuth2.get_id_email/get_profile call the People API
    (people.googleapis.com), which requires that API to be enabled and does not
    match our openid/email/profile scopes. Use the OIDC userinfo endpoint instead.
    """
    async with httpx.AsyncClient(timeout=USERINFO_TIMEOUT_SECONDS) as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        logger.warning(
            "oauth_google_userinfo_failed",
            extra={
                "stage": "oauth_google_identity_verified",
                "status_code": response.status_code,
            },
        )
        raise ValueError(f"Google userinfo failed with status {response.status_code}")
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Google userinfo returned an unexpected payload")
    return data


async def exchange_google_code(
    settings: Settings,
    *,
    code: str,
) -> tuple[str, str, dict[str, Any], str, str | None, int | None]:
    """
    Exchange authorization code for tokens + profile.

    Returns (google_id, email, profile, access_token, refresh_token, expires_at).
    """
    client = _google_client(settings)
    logger.info("oauth_code_exchange_started")
    token = await client.get_access_token(code, settings.GOOGLE_OAUTH_REDIRECT_URL)
    access_token = token["access_token"]
    refresh_token = token.get("refresh_token")
    if refresh_token is not None:
        refresh_token = str(refresh_token)
    expires_at = token.get("expires_at")
    if isinstance(expires_at, float):
        expires_at = int(expires_at)
    logger.info("oauth_code_exchange_completed")

    profile = await fetch_google_userinfo(access_token)
    google_id = str(profile.get("sub") or "").strip()
    email = str(profile.get("email") or "").strip()
    if not google_id:
        raise ValueError("Google account did not return a subject id")
    if not email:
        raise ValueError("Google account did not return an email address")
    if profile.get("email_verified") is False:
        raise ValueError("Google email is not verified")

    logger.info("oauth_google_identity_verified")
    return google_id, email, profile, access_token, refresh_token, expires_at


def oauth_configured(settings: Settings) -> bool:
    return bool(
        settings.GOOGLE_OAUTH_CLIENT_ID
        and settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value()
        and settings.GOOGLE_OAUTH_REDIRECT_URL
    )
