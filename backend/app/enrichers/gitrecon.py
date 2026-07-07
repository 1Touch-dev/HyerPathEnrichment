from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class GitReconEnricher(Enricher):
    source_name = "GitRecon"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username or request.email)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        username = request.username or (request.email or "candidate@example.com").split("@")[0]
        company = request.company or "Open Source Collective"
        return {
            "handles": [
                {
                    "platform": "GitHub",
                    "username": username,
                    "profile_url": f"https://github.com/{username}",
                    "confidence": 0.92,
                    "metadata": {"provider": self.source_name, "matched": True},
                }
            ],
            "github": {
                "profile": f"https://github.com/{username}",
                "organizations": [company, "Open Source Collective"],
                "public_commits": 128,
            },
            "sources": [self.source_name],
        }
