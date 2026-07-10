"""Config-selected backends that hide the free-vs-paid choice.

These providers are the only place that knows whether the system is running in
free/self-hosted mode or against a paid backend. Enrichers depend on the
providers, never on the concrete backend, so a free -> paid switch is an env
var flip (see ``config.py`` mode flags) with no enricher edits.
"""

from app.providers.browser import BrowserProvider
from app.providers.email_verify import EmailVerifier
from app.providers.linkedin_browser import (
    ExtractionMethod,
    LinkedInBrowserClient,
    LinkedInPhotoError,
    LinkedInPhotoResult,
    extract_linkedin_slug,
    is_placeholder_image_url,
    scrape_photo,
)
from app.providers.multilogin import MultiloginClient, MultiloginError
from app.providers.process import run_command
from app.providers.profile_pool import ProfileOutcome, ProfilePool, browser_semaphore
from app.providers.proxy import ProxyProvider
from app.providers.sidecar import SidecarClient

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
