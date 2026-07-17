"""Config-selected backends that hide the free-vs-paid choice.

These providers are the only place that knows whether the system is running in
free/self-hosted mode or against a paid backend. Enrichers depend on the
providers, never on the concrete backend, so a free -> paid switch is an env
var flip (see ``config.py`` mode flags) with no enricher edits.

LinkedIn/selenium symbols are exported lazily so ``from app.providers import
run_command`` (used by Tier 2–4 enrichers and unit tests) does not require
selenium on the host.
"""

from __future__ import annotations

from typing import Any

from app.providers.browser import BrowserProvider
from app.providers.email_verify import EmailVerifier
from app.providers.multilogin import MultiloginClient, MultiloginError
from app.providers.process import run_command
from app.providers.profile_pool import ProfileOutcome, ProfilePool, browser_semaphore
from app.providers.proxy import ProxyProvider
from app.providers.sidecar import SidecarClient

_LINKEDIN_EXPORTS = {
    "ExtractionMethod",
    "LinkedInBrowserClient",
    "LinkedInPhotoError",
    "LinkedInPhotoResult",
    "extract_linkedin_slug",
    "is_placeholder_image_url",
    "scrape_photo",
}

__all__ = [
    "BrowserProvider",
    "EmailVerifier",
    "ExtractionMethod",
    "LinkedInBrowserClient",
    "LinkedInPhotoError",
    "LinkedInPhotoResult",
    "MultiloginClient",
    "MultiloginError",
    "ProfileOutcome",
    "ProfilePool",
    "ProxyProvider",
    "SidecarClient",
    "browser_semaphore",
    "extract_linkedin_slug",
    "is_placeholder_image_url",
    "run_command",
    "scrape_photo",
]


def __getattr__(name: str) -> Any:
    if name in _LINKEDIN_EXPORTS:
        from app.providers import linkedin_browser as linkedin

        return getattr(linkedin, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
