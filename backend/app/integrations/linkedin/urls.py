"""LinkedIn URL parsing and placeholder detection."""

from __future__ import annotations

from urllib.parse import urlparse

from app.config import get_settings

from app.integrations.linkedin.constants import PLACEHOLDER_RE, PLACEHOLDER_SUBSTRINGS


def extract_linkedin_slug(url: str) -> str | None:
    """Parse ``/in/{slug}`` from a LinkedIn profile URL."""
    raw = (url or "").strip()
    if not raw:
        return None

    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if host != "linkedin.com":
        return None

    segments = [part for part in parsed.path.split("/") if part]
    if len(segments) < 2 or segments[0].lower() != "in":
        return None

    slug = segments[1].strip().lower()
    if not slug or slug in {"login", "signup", "authwall"}:
        return None
    return slug


def placeholder_fragments() -> tuple[str, ...]:
    """Built-in denylist plus optional comma-separated env extras."""
    settings = get_settings()
    extras = tuple(
        fragment.strip().lower()
        for fragment in settings.tier1_placeholder_denylist.split(",")
        if fragment.strip()
    )
    return PLACEHOLDER_SUBSTRINGS + extras


def is_placeholder_image_url(url: str) -> bool:
    """Return True when the image URL looks like a LinkedIn default avatar."""
    lowered = (url or "").strip().lower()
    if not lowered:
        return True

    for fragment in placeholder_fragments():
        if fragment in lowered:
            return True

    if PLACEHOLDER_RE.search(lowered):
        return True

    return False


def photo_url_from_srcset(srcset: str) -> str | None:
    """Return the highest-resolution URL from an img srcset attribute."""
    best_url: str | None = None
    best_width = 0

    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        pieces = part.split(" ", 1)
        url = pieces[0].strip()
        width = 0
        if len(pieces) > 1:
            size_str = pieces[1].strip().lower()
            if size_str.endswith("w"):
                try:
                    width = int(size_str[:-1])
                except ValueError:
                    pass
            elif size_str.endswith("x"):
                try:
                    width = int(size_str[:-1]) * 100
                except ValueError:
                    pass

        if url and width >= best_width:
            best_url = url
            best_width = width

    if best_url is None:
        for part in srcset.split(","):
            url = part.strip().split(" ", 1)[0].strip()
            if url:
                return url

    return best_url


def first_valid_photo_url(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate and not is_placeholder_image_url(candidate):
            return candidate
    return None
