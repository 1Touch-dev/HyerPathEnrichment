from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Architecture guide base scores for Tier 2 CLI hits (above DISAMBIGUATION_THRESHOLD).
SHERLOCK_HANDLE_CONFIDENCE = 0.75
MAIGRET_HANDLE_CONFIDENCE = 0.85


def extract_urls(text: str) -> list[str]:
    """Deduplicated profile URLs from CLI stdout (sherlock/maigret)."""
    seen: list[str] = []
    for url in _URL_RE.findall(text or ""):
        cleaned = url.rstrip(").,")
        # Skip proxy URLs that may contain credentials
        if "@" in cleaned and any(
            proxy_host in cleaned.lower()
            for proxy_host in ["oxylabs.io", "scrapoxy", "localhost:888"]
        ):
            continue
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


def urls_to_handles(
    username: str,
    urls: list[str],
    provider: str,
    *,
    confidence: float = 0.7,
) -> list[dict[str, Any]]:
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
                "confidence": confidence,
                "metadata": {"provider": provider, "matched": True},
            }
        )
    return handles


def slugify_domain(company: str | None) -> str:
    slug = re.sub(r"[^a-z0-9]", "", (company or "example").lower())
    return f"{slug or 'example'}.com"


_NAME_SPLIT_RE = re.compile(r"[\s._\-]+")
_LOCAL_PART_RE = re.compile(r"[^a-z]")


def split_person_name(raw: str) -> tuple[str, str | None]:
    """Split a free-form name/username into (first, last_or_none).

    Tokens are lowercased and stripped to a-z. Two or more tokens use the first
    and last token; a single token returns ``(token, None)``.
    """
    tokens = [
        _LOCAL_PART_RE.sub("", part.lower())
        for part in _NAME_SPLIT_RE.split((raw or "").strip())
        if part.strip()
    ]
    tokens = [token for token in tokens if token]
    if not tokens:
        return "candidate", None
    if len(tokens) == 1:
        return tokens[0], None
    return tokens[0], tokens[-1]


def common_email_patterns(name: str, domain: str, *, limit: int = 10) -> list[str]:
    """Prevalence-ordered corporate email guesses from a name + domain.

    Pure compute / offline fallback when email-sleuth is missing or returns
    nothing. Caps at ``limit`` (default 10) to match EMAIL_VERIFY_MAX_PER_JOB.
    """
    first, last = split_person_name(name)
    domain = (domain or "").strip().lower().lstrip("@")
    if not domain or not first:
        return []

    locals_: list[str]
    if last:
        f_initial = first[0]
        l_initial = last[0]
        locals_ = [
            f"{first}.{last}",
            f"{f_initial}{last}",
            f"{first}{last}",
            first,
            f"{first}_{last}",
            f"{first}-{last}",
            f"{f_initial}.{last}",
            f"{first}.{l_initial}",
            last,
            f"{last}.{first}",
        ]
    else:
        locals_ = [first]

    emails: list[str] = []
    seen: set[str] = set()
    for local in locals_:
        address = f"{local}@{domain}"
        if address in seen:
            continue
        seen.add(address)
        emails.append(address)
        if len(emails) >= max(1, limit):
            break
    return emails
