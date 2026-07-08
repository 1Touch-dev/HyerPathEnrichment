from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.enrichers._shared import extract_urls, urls_to_handles
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers import ProxyProvider, run_command


class MaigretEnricher(Enricher):
    source_name = "Maigret"

    def __init__(self) -> None:
        self.proxies = ProxyProvider()

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        # NOTE: maigret's programmatic API needs its site DB loaded; the CLI is
        # the stable seam. Proxy flows through unchanged when PROXY_MODE flips.
        settings = get_settings()
        username = request.username or ""
        args = ["maigret", "--no-color", "--print-found", username]
        proxy = self.proxies.get()
        if proxy:
            args[1:1] = ["--proxy", proxy]

        returncode, stdout, _ = await run_command(args, timeout=settings.maigret_timeout_seconds)
        if returncode not in (0, 124):
            return {}

        handles = urls_to_handles(username, extract_urls(stdout), self.source_name)
        return {"handles": handles} if handles else {}
