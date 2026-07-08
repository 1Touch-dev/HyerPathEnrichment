from __future__ import annotations

import re
from typing import Any

from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers import EmailVerifier


class EmailVerifyEnricher(Enricher):
    source_name = "Email Verify"

    def __init__(self) -> None:
        self.verifier = EmailVerifier()

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.email or request.username)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        email = request.email
        if not email and request.username:
            slug = re.sub(r"[^a-z0-9]", "", (request.company or "example").lower()) or "example"
            email = f"{request.username}@{slug}.com"

        verified = await self.verifier.verify(email or "")
        if verified is None:
            return {}
        return {"verified_emails": [verified]}
