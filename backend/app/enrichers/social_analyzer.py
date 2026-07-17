from __future__ import annotations

import uuid
from typing import Any

from app.core.config import get_settings
from app.enrichers.base import Enricher
from app.domain.enrichment import EnrichmentRequest
from app.providers import SidecarClient


def extract_social_analyzer_candidates(data: dict[str, Any]) -> list[Any]:
    """Return profile candidate rows from a Social Analyzer analyze_string payload."""
    user_info = data.get("user_info_normal")
    if isinstance(user_info, dict):
        candidates = user_info.get("data", [])
        if isinstance(candidates, list) and candidates:
            return candidates
    candidates = data.get("detected") or data.get("results") or []
    return candidates if isinstance(candidates, list) else []


def _parse_rate(raw: Any, default: float = 0.8) -> float:
    if raw is None or raw == "":
        return default
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().lstrip("%")
    try:
        return float(text)
    except ValueError:
        return default


class SocialAnalyzerEnricher(Enricher):
    source_name = "Social Analyzer"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        settings = get_settings()
        client = SidecarClient(settings.social_analyzer_url, timeout=180.0)
        data = await client.post_json(
            "/analyze_string",
            json={
                "string": request.username,
                "uuid": uuid.uuid4().hex,
                "option": ["FindUserProfilesFast"],
                "output": "json",
                "filter": ["all"],
                "profiles": ["detected"],
            },
        )
        if not isinstance(data, dict) or data == "Error":
            return {}

        candidates = extract_social_analyzer_candidates(data)

        handles: list[dict[str, Any]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            if str(item.get("good", "true")).lower() not in {"true", "1"}:
                continue
            url = item.get("link") or item.get("url")
            platform = item.get("type") or item.get("app") or item.get("platform")
            if not url or not platform:
                continue
            rate = _parse_rate(item.get("rate", 0.8) or 0.8)
            confidence = rate / 100 if rate > 1 else rate
            handles.append(
                {
                    "platform": str(platform),
                    "username": str(request.username),
                    "profile_url": str(url),
                    "confidence": confidence,
                    "metadata": {"provider": self.source_name, "matched": True},
                }
            )
        return {"handles": handles} if handles else {}
