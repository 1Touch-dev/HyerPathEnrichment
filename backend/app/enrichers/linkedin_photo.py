from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.enrichers.base import Enricher
from app.domain.enrichment import EnrichmentRequest
from app.domain.dossier import PhotoAsset
from app.observability.tier1_metrics import (
    tier1_cache_hits_total,
    tier1_cache_misses_total,
    tier1_scrape_total,
    tier1_upload_total,
)
from app.integrations.linkedin.urls import extract_linkedin_slug
from app.storage.photo_cache import PhotoCache
from app.storage.r2 import R2StorageClient, R2StorageError, object_key_with_extension


class LinkedInPhotoEnricher(Enricher):
    source_name = "linkedin-photo"

    def __init__(self) -> None:
        self.storage = R2StorageClient()
        self._browser: Any | None = None
        self.photo_cache = PhotoCache()

    @property
    def browser(self) -> Any:
        # Lazy: selenium lives in linkedin_browser; unit tests must not need it.
        if self._browser is None:
            from app.providers.linkedin_browser import LinkedInBrowserClient

            self._browser = LinkedInBrowserClient()
        return self._browser

    async def validate(self, request: EnrichmentRequest) -> bool:
        # Tier 1 is off by default: LinkedIn is the hardest to do free/safely.
        # Flip ENABLE_TIER1=true (and BROWSER_MODE=multilogin for prod) to run.
        return bool(request.linkedin_url) and get_settings().enable_tier1

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        linkedin_url = request.linkedin_url or ""
        slug = extract_linkedin_slug(linkedin_url)
        if not slug:
            return {}

        cached = await self.photo_cache.get(slug)
        if cached:
            tier1_cache_hits_total.inc()
            return {"photo": cached.model_dump(mode="json")}

        tier1_cache_misses_total.inc()
        result = await self.browser.scrape_photo(linkedin_url)
        tier1_scrape_total.labels(outcome=result.outcome.value).inc()
        if not result.image_bytes:
            return {}

        content_type = result.content_type or "image/jpeg"
        asset_key_base = f"linkedin/{slug}"
        try:
            asset_url = await self.storage.upload_bytes(
                asset_key_base,
                result.image_bytes,
                content_type=content_type,
            )
            tier1_upload_total.labels(result="success").inc()
        except R2StorageError:
            tier1_upload_total.labels(result="error").inc()
            return {}
        object_key = object_key_with_extension(asset_key_base, content_type)
        photo = PhotoAsset(
            source=self.source_name,
            asset_url=asset_url,
            captured_at=datetime.now(timezone.utc),
            confidence=result.confidence,
        )
        await self.photo_cache.put(
            slug,
            photo,
            asset_key=object_key,
            extraction_method=result.method.value if result.method else "",
            content_hash=hashlib.sha256(result.image_bytes).hexdigest(),
        )
        return {"photo": photo.model_dump(mode="json")}
