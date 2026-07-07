from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class SherlockEnricher(Enricher):
    source_name = "Sherlock"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        username = request.username or "candidate"
        return {
            "handles": [
                {
                    "platform": "X",
                    "username": username,
                    "profile_url": f"https://x.com/{username}",
                    "confidence": 0.75,
                    "metadata": {"provider": self.source_name, "matched": True},
                }
            ],
            "sources": [self.source_name],
        }
