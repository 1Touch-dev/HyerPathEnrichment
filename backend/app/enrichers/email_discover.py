from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.enrichers._shared import common_email_patterns, slugify_domain
from app.enrichers.base import Enricher
from app.domain.enrichment import EnrichmentRequest
from app.clients.process import run_command


class EmailDiscoverEnricher(Enricher):
    source_name = "Email Sleuth"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username or request.company)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        settings = get_settings()
        username = request.username or (request.email or "candidate").split("@")[0]
        domain = self._domain(request)

        emails = await self._email_sleuth(settings.email_sleuth_bin, username, domain)
        if not emails:
            # Pure-compute fallback: common corporate patterns, always free/offline.
            emails = common_email_patterns(username, domain)

        return {"emails": emails}

    async def _email_sleuth(self, binary: str, username: str, domain: str) -> list[str]:
        returncode, stdout, _ = await run_command(
            [binary, "--json", "--name", username, "--domain", domain],
            timeout=90.0,
        )
        if returncode != 0 or not stdout.strip():
            return []
        try:
            data = json.loads(stdout)
        except ValueError:
            return []
        candidates = data if isinstance(data, list) else data.get("emails", [])
        emails: list[str] = []
        for item in candidates:
            value = item.get("email") if isinstance(item, dict) else item
            if value:
                emails.append(str(value))
        return emails

    def _domain(self, request: EnrichmentRequest) -> str:
        if request.email and "@" in request.email:
            return request.email.split("@")[-1].lower()
        return slugify_domain(request.company)
