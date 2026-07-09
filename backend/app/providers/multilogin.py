"""Multilogin X API client for Tier 1 Selenium browser sessions.

Ports the senior ``follow.py`` sign-in + profile start pattern. Facebook feed
logic is intentionally omitted — this module only manages MLX auth and profile
lifecycle (start/stop/list).
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TOKEN_TTL_SECONDS = 25 * 60  # refresh before MLX ~30 min expiry


class MultiloginError(Exception):
    """Raised when a Multilogin API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MultiloginClient:
    """Async Multilogin client with cached bearer token."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @staticmethod
    def _json_headers(token: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def _launcher_v1_base(launcher_v2_url: str) -> str:
        base = launcher_v2_url.rstrip("/")
        if base.endswith("/api/v2"):
            return base[: -len("/api/v2")] + "/api/v1"
        return base.replace("/api/v2", "/api/v1")

    def _require_credentials(self) -> tuple[str, str, str]:
        settings = get_settings()
        email = settings.multilogin_email.strip()
        password = settings.multilogin_password.get_secret_value().strip()
        folder_id = settings.multilogin_folder_id.strip()
        if not email or not password or not folder_id:
            raise MultiloginError("Multilogin credentials or folder id not configured")
        return email, password, folder_id

    async def sign_in(self, *, force: bool = False) -> str:
        """Authenticate with MLX and return a bearer token."""
        if not force and self._token and time.monotonic() < self._token_expires_at:
            return self._token

        email, password, _folder_id = self._require_credentials()
        settings = get_settings()
        payload = {
            "email": email,
            "password": hashlib.md5(password.encode()).hexdigest(),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.multilogin_api_url.rstrip('/')}/user/signin",
                json=payload,
                headers=self._json_headers(),
            )

        if response.status_code != 200:
            logger.warning("Multilogin sign-in failed with status %s", response.status_code)
            raise MultiloginError("Multilogin sign-in failed", status_code=response.status_code)

        body = response.json()
        token = body.get("data", {}).get("token")
        if not token:
            raise MultiloginError("Multilogin sign-in response missing token")

        self._token = token
        self._token_expires_at = time.monotonic() + _TOKEN_TTL_SECONDS
        return token

    async def get_token(self) -> str:
        """Return a valid bearer token, refreshing when needed."""
        return await self.sign_in()

    async def start_profile(self, profile_id: str, token: str | None = None) -> int:
        """Start a browser profile for Selenium automation; return the local port."""
        settings = get_settings()
        _email, _password, folder_id = self._require_credentials()
        bearer = token or await self.get_token()

        url = (
            f"{settings.multilogin_launcher_url.rstrip('/')}"
            f"/profile/f/{folder_id}/p/{profile_id}/start"
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                params={"automation_type": "selenium"},
                headers=self._json_headers(bearer),
            )

        if response.status_code != 200:
            logger.warning(
                "Multilogin start_profile failed for profile %s (status %s)",
                profile_id,
                response.status_code,
            )
            raise MultiloginError(
                f"Failed to start Multilogin profile {profile_id}",
                status_code=response.status_code,
            )

        body = response.json()
        port = body.get("data", {}).get("port")
        if port is None:
            raise MultiloginError(f"Multilogin start_profile missing port for {profile_id}")
        return int(port)

    async def stop_profile(self, profile_id: str, token: str | None = None) -> None:
        """Stop a running browser profile."""
        settings = get_settings()
        bearer = token or await self.get_token()
        v1_base = self._launcher_v1_base(settings.multilogin_launcher_url)
        url = f"{v1_base}/profile/stop/p/{profile_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._json_headers(bearer))

        if response.status_code != 200:
            logger.warning(
                "Multilogin stop_profile failed for profile %s (status %s)",
                profile_id,
                response.status_code,
            )
            raise MultiloginError(
                f"Failed to stop Multilogin profile {profile_id}",
                status_code=response.status_code,
            )

    async def list_profiles(self, token: str | None = None) -> list[str]:
        """Return profile IDs in the configured MLX folder."""
        settings = get_settings()
        _email, _password, folder_id = self._require_credentials()
        bearer = token or await self.get_token()

        profile_ids: list[str] = []
        offset = 0
        page_size = 100
        pool_cap = settings.multilogin_profile_pool_size

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                payload: dict[str, Any] = {
                    "limit": page_size,
                    "offset": offset,
                    "folder_id": folder_id,
                }
                response = await client.post(
                    f"{settings.multilogin_api_url.rstrip('/')}/profile/search",
                    json=payload,
                    headers=self._json_headers(bearer),
                )
                if response.status_code != 200:
                    logger.warning("Multilogin profile search failed (status %s)", response.status_code)
                    raise MultiloginError(
                        "Failed to list Multilogin profiles",
                        status_code=response.status_code,
                    )

                data = response.json().get("data", {})
                profiles = data.get("profiles") or []
                for profile in profiles:
                    profile_id = profile.get("profile_id") or profile.get("id")
                    if profile_id:
                        profile_ids.append(str(profile_id))
                        if pool_cap > 0 and len(profile_ids) >= pool_cap:
                            return profile_ids

                total = int(data.get("total") or 0)
                offset += len(profiles)
                if not profiles or offset >= total:
                    break

        return profile_ids


_default_client = MultiloginClient()


async def sign_in(*, force: bool = False) -> str:
    return await _default_client.sign_in(force=force)


async def get_token() -> str:
    return await _default_client.get_token()


async def start_profile(profile_id: str, token: str | None = None) -> int:
    return await _default_client.start_profile(profile_id, token)


async def stop_profile(profile_id: str, token: str | None = None) -> None:
    await _default_client.stop_profile(profile_id, token)


async def list_profiles(token: str | None = None) -> list[str]:
    return await _default_client.list_profiles(token)
