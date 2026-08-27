"""Public (unauthenticated) HTTP schemas for the brands module. Separated from
schemas.py the same way portfolio/schemas.py separates PublicPortfolioResponse
from the authenticated PortfolioProfileResponse — this is the response shape
served to anonymous visitors of a brand's landing page, so it must never leak
custom_domain, chatbot_config, or any internal id (see
docs/adr/0019-tenancy-model.md)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PublicBrandResponse(BaseModel):
    """What an unauthenticated visitor to a brand's landing page sees — no id,
    no custom_domain, no chatbot_config. landing_page_tier_config is
    brand-authored marketing copy (not internal configuration), so it is safe
    to serve in full."""

    name: str
    slug: str
    landing_page_tier_config: dict[str, Any] | None
