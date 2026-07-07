from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class TheHarvesterEnricher(Enricher):
    source_name = "theHarvester"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.company or request.email)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        domain = (request.email or "candidate@example.com").split("@")[-1]
        local_part = (request.email or "candidate@example.com").split("@")[0]
        return {
            "emails": [request.email or f"{local_part}@{domain}"],
            "sources": [self.source_name],
        }
