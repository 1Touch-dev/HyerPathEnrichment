from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class SocialAnalyzerEnricher(Enricher):
    source_name = "Social Analyzer"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        username = request.username or "candidate"
        return {
            "handles": [
                {
                    "platform": "LinkedIn",
                    "username": username,
                    "profile_url": f"https://linkedin.com/in/{username}",
                    "confidence": 0.88,
                    "metadata": {"provider": self.source_name, "matched": True},
                }
            ],
            "sources": [self.source_name],
        }
