from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class MaigretEnricher(Enricher):
    source_name = "Maigret"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        username = request.username or "candidate"
        return {
            "handles": [
                {
                    "platform": "Reddit",
                    "username": username,
                    "profile_url": f"https://reddit.com/u/{username}",
                    "confidence": 0.71,
                    "metadata": {"provider": self.source_name, "matched": True},
                }
            ],
            "sources": [self.source_name],
        }
