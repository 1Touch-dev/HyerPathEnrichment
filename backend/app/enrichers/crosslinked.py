from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.enrichers._shared import extract_emails, slugify_domain
from app.enrichers.base import Enricher
from app.domain.enrichment import EnrichmentRequest
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
        search = settings.crosslinked_search_engines.strip() or "yahoo"
        outfile = "crosslinked_names"

        args = [
            "crosslinked",
            "--search",
            search,
            "-f",
            f"{{first}}.{{last}}@{domain}",
            "-o",
            outfile,
            company,
        ]
        proxy = self.proxies.get()
        if proxy:
            args[1:1] = ["--proxy", proxy]

        with tempfile.TemporaryDirectory() as tmp:
            returncode, stdout, _ = await run_command(
                args,
                timeout=settings.crosslinked_timeout_seconds,
                cwd=tmp,
            )
            if returncode not in (0, 124):
                return {}

            emails = self._collect_emails(stdout, Path(tmp) / f"{outfile}.txt")

        coworkers = self._names_from_emails(emails)
        fragment: dict[str, Any] = {}
        if coworkers:
            fragment["coworkers"] = coworkers
        if emails:
            fragment["emails"] = emails
        return fragment

    @staticmethod
    def _collect_emails(stdout: str, names_file: Path) -> list[str]:
        seen: set[str] = set()
        emails: list[str] = []

        def add(raw: str) -> None:
            normalized = raw.strip().lower()
            if not normalized or "@" not in normalized or normalized in seen:
                return
            seen.add(normalized)
            emails.append(normalized)

        for email in extract_emails(stdout):
            add(email)

        if names_file.is_file():
            for line in names_file.read_text(encoding="utf-8", errors="replace").splitlines():
                for email in extract_emails(line):
                    add(email)

        return emails

    def _names_from_emails(self, emails: list[str]) -> list[str]:
        names: list[str] = []
        for email in emails:
            local = email.split("@")[0]
            parts = [part.capitalize() for part in local.replace(".", " ").split() if part]
            full = " ".join(parts)
            if full and full not in names:
                names.append(full)
        return names
