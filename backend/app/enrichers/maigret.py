from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.enrichers._shared import MAIGRET_HANDLE_CONFIDENCE, extract_urls, urls_to_handles
from app.enrichers.base import Enricher
from app.domain.enrichment import EnrichmentRequest
from app.clients.proxy import ProxyProvider
from app.clients.process import run_command


class MaigretEnricher(Enricher):
    source_name = "Maigret"

    def __init__(self) -> None:
        self.proxies = ProxyProvider()

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        # NOTE: maigret's programmatic API needs its site DB loaded; the CLI is
        # the stable seam. Proxy flows through unchanged when PROXY_MODE flips.
        # Maigret >=0.6 dropped --print-found; found accounts still print as
        # "[+] Site: https://..." on stdout. Cap sites so default timeouts finish.
        settings = get_settings()
        username = request.username or ""
        args = [
            "maigret",
            "--no-color",
            "--no-progressbar",
            "--top-sites",
            "150",
            username,
        ]
        proxy = self.proxies.get()
        if proxy:
            args[1:1] = ["--proxy", proxy]

        returncode, stdout, stderr = await run_command(
            args, timeout=settings.maigret_timeout_seconds
        )
        if returncode not in (0, 124):
            return {}

        # Prefer stdout; some environments merge progress onto stderr.
        combined = "\n".join(part for part in (stdout, stderr) if part)
        handles = urls_to_handles(
            username,
            extract_urls(combined),
            self.source_name,
            confidence=MAIGRET_HANDLE_CONFIDENCE,
        )
        return {"handles": handles} if handles else {}
