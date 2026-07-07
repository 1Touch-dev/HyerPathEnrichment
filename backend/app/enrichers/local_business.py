from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class LocalBusinessEnricher(Enricher):
    source_name = "Google Maps Scraper"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.business)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        business_name = request.business or "Example Business"
        return {
            "business": {
                "name": business_name,
                "address": "123 Market Street, San Francisco, CA",
                "website": "https://www.example-business.com",
                "rating": 4.7,
                "phone": "+1 (415) 555-0133",
                "metadata": {"provider": self.source_name},
            },
            "sources": [self.source_name],
        }
