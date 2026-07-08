from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.enrichers._shared import extract_emails, slugify_domain
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers import ProxyProvider, run_command


class CrossLinkedEnricher(Enricher):
    source_name = "CrossLinked"

    def __init__(self) -> None:
        self.proxies = ProxyProvider()

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.company)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        settings = get_settings()
        company = request.company or ""
        domain = slugify_domain(company)
        args = ["crosslinked", "-f", f"{{first}}.{{last}}@{domain}", company]
        proxy = self.proxies.get()
        if proxy:
            args[1:1] = ["--proxy", proxy]

        returncode, stdout, _ = await run_command(args, timeout=settings.crosslinked_timeout_seconds)
        if returncode not in (0, 124):
            return {}

        emails = extract_emails(stdout)
        coworkers = self._names_from_emails(emails)
        fragment: dict[str, Any] = {}
        if coworkers:
            fragment["coworkers"] = coworkers
        if emails:
            fragment["emails"] = emails
        return fragment

    def _names_from_emails(self, emails: list[str]) -> list[str]:
        names: list[str] = []
        for email in emails:
            local = email.split("@")[0]
            parts = [part.capitalize() for part in local.replace(".", " ").split() if part]
            full = " ".join(parts)
            if full and full not in names:
                names.append(full)
        return names
