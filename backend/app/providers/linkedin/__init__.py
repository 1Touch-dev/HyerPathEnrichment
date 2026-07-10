"""LinkedIn profile photo scraping via Selenium + Multilogin."""

from app.providers.linkedin.client import LinkedInBrowserClient, scrape_photo
from app.providers.linkedin.login import (
    connect_selenium,
    detect_page_state,
    has_valid_linkedin_session,
    login_linkedin,
)
from app.providers.linkedin.photo import extract_photo_url, save_failure_screenshot
from app.providers.linkedin.scrape import download_image, scrape_on_driver
from app.providers.linkedin.types import (
    ExtractionMethod,
    LinkedInPhotoError,
    LinkedInPhotoResult,
    NO_RETRY_OUTCOMES,
    ROTATE_PROFILE_OUTCOMES,
)
from app.providers.linkedin.urls import (
    extract_linkedin_slug,
    is_placeholder_image_url,
    placeholder_fragments,
    photo_url_from_srcset,
)

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
