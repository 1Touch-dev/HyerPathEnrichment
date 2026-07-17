from __future__ import annotations

import logging
from typing import Any

import httpx

from app.clients.retry import with_transient_retry

logger = logging.getLogger(__name__)


class SidecarClient:
    """Thin async HTTP client for all AGPL/self-hosted sidecars.

    The free-vs-paid difference for a sidecar is only its URL: unset or
    unreachable resolves to ``None`` so the calling enricher returns a valid
    empty fragment instead of failing. AGPL tools stay isolated behind HTTP
    (never imported into ``app/``), per the architecture rules.
    """

    def __init__(self, base_url: str | None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or "").strip().rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def get_json(
        self,
        path: str = "",
        params: dict[str, Any] | None = None,
    ) -> Any | None:
        if not self.enabled:
            return None
        url = f"{self.base_url}{path}"

        async def _do() -> Any:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()

        try:
            return await with_transient_retry(_do, max_retries=2)
        except (httpx.HTTPError, ValueError):
            logger.warning("sidecar GET failed: %s", self.base_url, exc_info=True)
            return None

    async def post_json(
        self,
        path: str = "",
        json: dict[str, Any] | None = None,
    ) -> Any | None:
        if not self.enabled:
            return None
        url = f"{self.base_url}{path}"

        async def _do() -> Any:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=json)
                response.raise_for_status()
                return response.json()

        try:
            return await with_transient_retry(_do, max_retries=2)
        except (httpx.HTTPError, ValueError):
            logger.warning("sidecar POST failed: %s", self.base_url, exc_info=True)
            return None

    async def get_text(self, path: str = "") -> str | None:
        if not self.enabled:
            return None
        url = f"{self.base_url}{path}"

        async def _do() -> str:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text

        try:
            return await with_transient_retry(_do, max_retries=2)
        except httpx.HTTPError:
            logger.warning("sidecar GET text failed: %s", self.base_url, exc_info=True)
            return None
