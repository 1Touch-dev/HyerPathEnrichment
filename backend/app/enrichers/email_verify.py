from __future__ import annotations

import asyncio
import re
from typing import Any

from app.config import get_settings
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers import EmailVerifier


class EmailVerifyEnricher(Enricher):
    source_name = "Email Verify"

    def __init__(self) -> None:
        self.verifier = EmailVerifier()

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.email or request.username)

    async def verify_emails(self, emails: list[str]) -> dict[str, Any]:
        """Verify a batch of addresses using the configured EMAIL_VERIFY_LEVEL chain."""
        settings = get_settings()
        smtp_mode = settings.email_verify_level.strip().lower() == "smtp"
        delay = max(0, settings.email_verify_smtp_delay_seconds)
        verified: list[dict[str, Any]] = []

        for index, raw in enumerate(emails):
            if index > 0 and smtp_mode and delay > 0:
                await asyncio.sleep(delay)
            result = await self.verifier.verify(raw)
            if result is not None:
                verified.append(result)

        if not verified:
            return {}
        return {"verified_emails": verified, "sources": [self.source_name]}

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        emails: list[str] = []
        if request.email:
            emails.append(request.email)
        elif request.username:
            slug = re.sub(r"[^a-z0-9]", "", (request.company or "example").lower()) or "example"
            emails.append(f"{request.username}@{slug}.com")
        if not emails:
            return {}
        return await self.verify_emails(emails)
