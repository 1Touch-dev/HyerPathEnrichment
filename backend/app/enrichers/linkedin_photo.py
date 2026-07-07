from datetime import datetime, timezone

from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.storage.r2 import R2StorageClient


class LinkedInPhotoEnricher(Enricher):
    source_name = "linkedin-photo"

    def __init__(self) -> None:
        self.storage = R2StorageClient()

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.linkedin_url)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        username = (request.username or "profile").strip().lower()
        asset_key = f"linkedin/{username}.jpg"
        asset_url = await self.storage.upload_bytes(asset_key, b"mock-image-bytes", content_type="image/jpeg")
        return {
            "photo": {
                "source": self.source_name,
                "asset_url": asset_url,
                "captured_at": datetime.now(timezone.utc),
                "confidence": 0.84,
            },
            "sources": [self.source_name],
        }
