"""Backward-compatible facade for LinkedIn browser scraping.

Implementation lives in ``app.providers.linkedin``; import from this module
or from the package interchangeably.
"""

from __future__ import annotations

import asyncio

from selenium.webdriver.common.action_chains import ActionChains

from app.providers.linkedin.client import LinkedInBrowserClient, scrape_photo
from app.providers.linkedin.login import (
    connect_selenium,
    detect_page_state,
    find_login_input,
    find_sign_in_button,
    has_valid_linkedin_session,
    login_linkedin,
    sign_in_button_enabled,
    type_into_login_field,
    wait_for_enabled_sign_in_button,
)
from app.providers.linkedin.photo import (
    extract_photo_url,
    save_failure_screenshot,
    wait_for_profile_photo_ready,
)
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
from app.providers.profile_pool import browser_semaphore

# Legacy private names used by tests and scripts.
_find_login_input = find_login_input
_find_sign_in_button = find_sign_in_button
_photo_url_from_srcset = photo_url_from_srcset
_scrape_on_driver = scrape_on_driver
_sign_in_button_enabled = sign_in_button_enabled
_type_into_login_field = type_into_login_field
_wait_for_enabled_sign_in_button = wait_for_enabled_sign_in_button
_wait_for_profile_photo_ready = wait_for_profile_photo_ready

__all__ = [
    "ActionChains",
    "ExtractionMethod",
    "LinkedInBrowserClient",
    "LinkedInPhotoError",
    "LinkedInPhotoResult",
    "NO_RETRY_OUTCOMES",
    "ROTATE_PROFILE_OUTCOMES",
    "_find_login_input",
    "_find_sign_in_button",
    "_photo_url_from_srcset",
    "_scrape_on_driver",
    "_sign_in_button_enabled",
    "_type_into_login_field",
    "_wait_for_enabled_sign_in_button",
    "_wait_for_profile_photo_ready",
    "asyncio",
    "browser_semaphore",
    "connect_selenium",
    "detect_page_state",
    "download_image",
    "extract_linkedin_slug",
    "extract_photo_url",
    "has_valid_linkedin_session",
    "is_placeholder_image_url",
    "login_linkedin",
    "placeholder_fragments",
    "save_failure_screenshot",
    "scrape_photo",
]
