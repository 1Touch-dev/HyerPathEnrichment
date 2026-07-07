from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class JobSpyEnricher(Enricher):
    source_name = "JobSpy"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.job_search)

    async def run(self, request: EnrichmentRequest) -> dict[str, object]:
        return {
            "jobs": [
                {
                    "title": request.job_search or "Staff Backend Engineer",
                    "company": request.company or "Hyrepath Labs",
                    "location": "Remote",
                    "remote": True,
                    "source": self.source_name,
                }
            ],
            "sources": [self.source_name],
        }
