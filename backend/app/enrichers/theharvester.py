from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.enrichers._shared import extract_emails
from app.enrichers.base import Enricher
from app.domain.enrichment import EnrichmentRequest
from app.clients.proxy import ProxyProvider
from app.clients.process import run_command


class TheHarvesterEnricher(Enricher):
    source_name = "theHarvester"

    def __init__(self) -> None:
        self.proxies = ProxyProvider()

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.company or request.email)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        settings = get_settings()
        domain = self._domain(request)
        if not domain:
            return {}

        # ProxyProvider is consulted so free/paid parity is preserved; direct
        # in free mode. theHarvester reads proxies from its own config file, so
        # we only gate here rather than pass a flag.
        _ = self.proxies.get()
        returncode, stdout, _stderr = await run_command(
            ["theHarvester", "-d", domain, "-l", "100", "-b", "duckduckgo"],
            timeout=settings.theharvester_timeout_seconds,
        )
        if returncode not in (0, 124):
            return {}

        emails = extract_emails(stdout)
        return {"emails": emails} if emails else {}

    def _domain(self, request: EnrichmentRequest) -> str:
        if request.email and "@" in request.email:
            return request.email.split("@")[-1]
        if request.company:
            import re

            slug = re.sub(r"[^a-z0-9]", "", request.company.lower())
            return f"{slug}.com" if slug else ""
        return ""
