from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class CrossLinkedEnricher(Enricher):
    source_name = "CrossLinked"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.company)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        return {
            "coworkers": ["Jamie Flores", "Morgan Lee", "Taylor Patel"],
            "sources": [self.source_name],
        }
