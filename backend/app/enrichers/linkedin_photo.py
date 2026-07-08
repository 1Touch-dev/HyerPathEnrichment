from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers import BrowserProvider, ProxyProvider
from app.storage.r2 import R2StorageClient


class LinkedInPhotoEnricher(Enricher):
    source_name = "linkedin-photo"

    def __init__(self) -> None:
        self.storage = R2StorageClient()
        self.proxies = ProxyProvider()

    async def validate(self, request: EnrichmentRequest) -> bool:
        # Tier 1 is off by default: LinkedIn is the hardest to do free/safely.
        # Flip ENABLE_TIER1=true (and BROWSER_MODE=multilogin for prod) to run.
        return bool(request.linkedin_url) and get_settings().enable_tier1

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        browser = BrowserProvider(proxy=self.proxies.get())
        image_url: str | None = None
        async with browser.page() as page:
            if page is None:
                return {}
            await page.goto(request.linkedin_url, wait_until="domcontentloaded")
            image_url = await page.get_attribute('meta[property="og:image"]', "content")

        if not image_url:
            return {}

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_bytes = response.content
        except httpx.HTTPError:
            return {}

        username = (request.username or "profile").strip().lower()
        asset_url = await self.storage.upload_bytes(
            f"linkedin/{username}.jpg", image_bytes, content_type="image/jpeg"
        )
        return {
            "photo": {
                "source": self.source_name,
                "asset_url": asset_url,
                "captured_at": datetime.now(timezone.utc),
                "confidence": 0.84,
            }
        }
