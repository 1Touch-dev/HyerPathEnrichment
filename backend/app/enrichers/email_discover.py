from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class EmailDiscoverEnricher(Enricher):
    source_name = "Email Sleuth"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username or request.company)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        username = request.username or "candidate"
        company_slug = (request.company or "example").replace(" ", "").lower()
        return {
            "emails": [f"{username}@{company_slug}.com"],
            "sources": [self.source_name],
        }
