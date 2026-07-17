"""Compatibility shim ? prefer app.integrations.linkedin.

Only re-export URL/type helpers eagerly so importing this package (or
``app.providers.linkedin.urls``) does not require selenium. Selenium-backed
symbols stay lazy via ``__getattr__``.
"""

from __future__ import annotations

from typing import Any

from app.integrations.linkedin.types import (
    ExtractionMethod,
    LinkedInPhotoError,
    LinkedInPhotoResult,
    NO_RETRY_OUTCOMES,
    ROTATE_PROFILE_OUTCOMES,
)
from app.integrations.linkedin.urls import (
    extract_linkedin_slug,
    is_placeholder_image_url,
    placeholder_fragments,
    photo_url_from_srcset,
)

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "LinkedInBrowserClient": ("app.integrations.linkedin.client", "LinkedInBrowserClient"),
    "scrape_photo": ("app.integrations.linkedin.client", "scrape_photo"),
    "connect_selenium": ("app.integrations.linkedin.login", "connect_selenium"),
    "detect_page_state": ("app.integrations.linkedin.login", "detect_page_state"),
    "has_valid_linkedin_session": ("app.integrations.linkedin.login", "has_valid_linkedin_session"),
    "login_linkedin": ("app.integrations.linkedin.login", "login_linkedin"),
    "extract_photo_url": ("app.integrations.linkedin.photo", "extract_photo_url"),
    "save_failure_screenshot": ("app.integrations.linkedin.photo", "save_failure_screenshot"),
    "download_image": ("app.integrations.linkedin.scrape", "download_image"),
    "scrape_on_driver": ("app.integrations.linkedin.scrape", "scrape_on_driver"),
}

__all__ = [
    "ExtractionMethod",
    "LinkedInBrowserClient",
    "LinkedInPhotoError",
    "LinkedInPhotoResult",
    "NO_RETRY_OUTCOMES",
    "ROTATE_PROFILE_OUTCOMES",
    "connect_selenium",
    "detect_page_state",
    "download_image",
    "extract_linkedin_slug",
    "extract_photo_url",
    "has_valid_linkedin_session",
    "is_placeholder_image_url",
    "login_linkedin",
    "photo_url_from_srcset",
    "placeholder_fragments",
    "save_failure_screenshot",
    "scrape_on_driver",
    "scrape_photo",
]


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    import importlib

    module = importlib.import_module(module_name)
    value = getattr(module, attr)
    globals()[name] = value
    return value
