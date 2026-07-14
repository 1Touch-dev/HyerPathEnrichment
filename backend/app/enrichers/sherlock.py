from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.enrichers._shared import SHERLOCK_HANDLE_CONFIDENCE, extract_urls, urls_to_handles
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers import ProxyProvider, run_command


class SherlockEnricher(Enricher):
    source_name = "Sherlock"

    def __init__(self) -> None:
        self.proxies = ProxyProvider()

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        # NOTE: sherlock ships a CLI; we shell out for stability rather than
        # driving its internal QueryNotify API. Proxy flows through unchanged.
        settings = get_settings()
        username = request.username or ""
        args = ["sherlock", "--print-found", "--no-color", "--timeout", "10", username]
        proxy = self.proxies.get()
        if proxy:
            args[1:1] = ["--proxy", proxy]

        returncode, stdout, _ = await run_command(args, timeout=settings.sherlock_timeout_seconds)
        if returncode not in (0, 124):
            return {}

        handles = urls_to_handles(
            username,
            extract_urls(stdout),
            self.source_name,
            confidence=SHERLOCK_HANDLE_CONFIDENCE,
        )
        return {"handles": handles} if handles else {}
