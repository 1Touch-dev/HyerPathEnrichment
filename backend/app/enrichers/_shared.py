from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def extract_urls(text: str) -> list[str]:
    """Deduplicated profile URLs from CLI stdout (sherlock/maigret)."""
    seen: list[str] = []
    for url in _URL_RE.findall(text or ""):
        cleaned = url.rstrip(").,")
        if cleaned not in seen:
            seen.append(cleaned)
    return seen


def extract_emails(text: str) -> list[str]:
    """Deduplicated, lowercased emails from CLI stdout (theHarvester)."""
    seen: list[str] = []
    for email in _EMAIL_RE.findall(text or ""):
        normalized = email.lower()
        if normalized not in seen:
            seen.append(normalized)
    return seen


def urls_to_handles(username: str, urls: list[str], provider: str) -> list[dict[str, Any]]:
    """Map discovered profile URLs to SocialHandle-shaped dicts."""
    handles: list[dict[str, Any]] = []
    for url in urls:
        host = urlsplit(url).netloc.lower()
        platform = host[4:] if host.startswith("www.") else host
        platform = platform.split(".")[0].capitalize() if platform else "Unknown"
        handles.append(
            {
                "platform": platform,
                "username": username,
                "profile_url": url,
                "confidence": 0.7,
                "metadata": {"provider": provider, "matched": True},
            }
        )
    return handles


def slugify_domain(company: str | None) -> str:
    slug = re.sub(r"[^a-z0-9]", "", (company or "example").lower())
    return f"{slug or 'example'}.com"
