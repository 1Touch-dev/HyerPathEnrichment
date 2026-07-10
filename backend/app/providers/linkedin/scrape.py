"""LinkedIn scrape orchestration on an active Selenium driver."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from selenium.webdriver.support.ui import WebDriverWait

from app.config import get_settings
from app.providers.linkedin.constants import DOM_FALLBACK_CONFIDENCE, OG_IMAGE_CONFIDENCE
from app.providers.linkedin.login import detect_page_state, login_linkedin
from app.providers.linkedin.photo import (
    extract_photo_url,
    log_photo_extraction_debug,
    save_failure_screenshot,
    wait_for_profile_photo_ready,
)
from app.providers.linkedin.types import ExtractionMethod, LinkedInPhotoError, LinkedInPhotoResult
from app.providers.profile_pool import ProfileOutcome

logger = logging.getLogger(__name__)


async def download_image(url: str) -> tuple[bytes | None, str | None]:
    """Download image bytes for a photo URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            return response.content, content_type or "image/jpeg"
    except httpx.HTTPError:
        logger.warning("LinkedIn photo download failed", exc_info=True)
        return None, None


def scrape_on_driver(driver: Any, linkedin_url: str) -> tuple[LinkedInPhotoResult, str | None]:
    """Selenium-only scrape steps once a driver is connected."""
    settings = get_settings()
    logger.debug("Starting scrape for %s", linkedin_url)

    login_state = login_linkedin(driver)
    logger.debug(
        "Login returned %s url=%s title=%s",
        login_state,
        driver.current_url,
        driver.title,
    )

    if login_state not in {LinkedInPhotoError.SUCCESS, LinkedInPhotoError.AUTH_REQUIRED}:
        return LinkedInPhotoResult(outcome=login_state), None

    if login_state == LinkedInPhotoError.AUTH_REQUIRED:
        return LinkedInPhotoResult(outcome=LinkedInPhotoError.AUTH_REQUIRED), None

    logger.debug("Navigating to profile %s", linkedin_url)
    driver.get(linkedin_url)
    logger.debug(
        "Navigation finished url=%s title=%s",
        driver.current_url,
        driver.title,
    )

    page_state = detect_page_state(driver)
    logger.debug("Detected page state %s url=%s", page_state, driver.current_url)
    if page_state != LinkedInPhotoError.SUCCESS:
        return LinkedInPhotoResult(outcome=page_state), None

    wait = WebDriverWait(driver, settings.tier1_browser_timeout_seconds)
    try:
        wait_for_profile_photo_ready(driver, wait)
    except Exception:
        logger.warning("Timed out waiting for profile photo DOM", exc_info=True)

    image_url, method, extract_state = extract_photo_url(driver)
    if extract_state != LinkedInPhotoError.SUCCESS or not image_url or method is None:
        if extract_state in {LinkedInPhotoError.NO_IMAGE, LinkedInPhotoError.PLACEHOLDER_IMAGE}:
            log_photo_extraction_debug(driver)
            save_failure_screenshot(driver, None)
        return LinkedInPhotoResult(outcome=extract_state), None

    confidence = OG_IMAGE_CONFIDENCE if method == ExtractionMethod.OG_IMAGE else DOM_FALLBACK_CONFIDENCE
    return (
        LinkedInPhotoResult(
            outcome=LinkedInPhotoError.SUCCESS,
            method=method,
            confidence=confidence,
        ),
        image_url,
    )


def map_outcome_to_profile(outcome: LinkedInPhotoError) -> ProfileOutcome | None:
    mapping = {
        LinkedInPhotoError.CAPTCHA: ProfileOutcome.CAPTCHA,
        LinkedInPhotoError.AUTH_REQUIRED: ProfileOutcome.AUTH_REQUIRED,
        LinkedInPhotoError.RATE_LIMITED: ProfileOutcome.RATE_LIMITED,
        LinkedInPhotoError.TEMPORARY_FAILURE: ProfileOutcome.TEMPORARY_FAILURE,
        LinkedInPhotoError.NOT_FOUND: ProfileOutcome.NOT_FOUND,
        LinkedInPhotoError.INVALID_URL: ProfileOutcome.INVALID_URL,
        LinkedInPhotoError.SUCCESS: ProfileOutcome.SUCCESS,
    }
    return mapping.get(outcome)
