"""Canonical identifier normalization for suppression, purge, and audit hashing."""

from __future__ import annotations

import hashlib
import re

from app.models import EnrichmentRequest
from app.providers.linkedin.urls import extract_linkedin_slug

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_identifier(raw: str) -> str:
    """Return a stable string used for hashing and equality checks.

    LinkedIn profile URLs collapse to ``linkedin:{slug}`` so variants like
    ``https://www.linkedin.com/in/jane`` and ``linkedin.com/in/jane/`` match.
    """
    value = (raw or "").strip()
    if not value:
        return ""

    slug = extract_linkedin_slug(value)
    if slug:
        return f"linkedin:{slug}"

    return value.lower()


def hash_identifier(raw: str) -> str:
    """SHA-256 of the normalized identifier (never store raw PII in audit tables)."""
    normalized = normalize_identifier(raw)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def linkedin_slug_from_identifier(raw: str) -> str | None:
    """Return the LinkedIn profile slug when *raw* is a profile URL, else None."""
    normalized = normalize_identifier(raw)
    if normalized.startswith("linkedin:"):
        return normalized.removeprefix("linkedin:")
    return None


def request_identifier_values(request: EnrichmentRequest) -> list[str]:
    """All non-empty identifier fields from an enrichment request."""
    return [
        value
        for value in (
            request.email,
            request.linkedin_url,
            request.username,
            request.company,
            request.business,
            request.job_search,
        )
        if value
    ]


def hashes_from_request(request: EnrichmentRequest) -> list[str]:
    """Unique SHA-256 hashes for every identifier on the request."""
    seen: set[str] = set()
    hashes: list[str] = []
    for value in request_identifier_values(request):
        digest = hash_identifier(value)
        if digest not in seen:
            seen.add(digest)
            hashes.append(digest)
    return hashes


def looks_like_email(raw: str) -> bool:
    """Quick check used only for normalization hints (not validation)."""
    return bool(_EMAIL_RE.match((raw or "").strip().lower()))
