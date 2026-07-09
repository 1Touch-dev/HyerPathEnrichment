"""LinkedIn profile photo scraping via Selenium + Multilogin."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.providers.multilogin import MultiloginClient, MultiloginError
from app.providers.profile_pool import ProfileOutcome, ProfilePool, browser_semaphore

logger = logging.getLogger(__name__)

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"
OG_IMAGE_CONFIDENCE = 0.84
DOM_FALLBACK_CONFIDENCE = 0.70
ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "tier1"

PLACEHOLDER_SUBSTRINGS = (
    "ghost-person",
    "ghost_person",
    "default-avatar",
    "default_avatar",
    "static-exp1/static/img/person",
    "static.licdn.com/aero-v1/sc/h/",
    "/images/ghost",
    "profile-displayphoto-shrink_100_100/0",
    "profile-displayphoto-shrink_200_200/0",
    "profile-displayphoto-default",
    "blank-profile",
    "silhouette",
    "company-logo",
    "licdn.com/dms/image/c4e03aq",  # common LI placeholder hash prefix
    "data:image/gif;base64",
    "data:image/svg",
)

DOM_PHOTO_SELECTORS = (
    "img.pv-top-card-profile-picture__image--show",
    "img.pv-top-card-profile-picture__image",
    "img.profile-photo-edit__preview",
    "img[data-delayed-url]",
    "img.top-card-layout__entity-image",
)


class LinkedInPhotoError(StrEnum):
    SUCCESS = "success"
    INVALID_URL = "invalid_url"
    NOT_FOUND = "not_found"
    AUTH_REQUIRED = "auth_required"
    CAPTCHA = "captcha"
    RATE_LIMITED = "rate_limited"
    TEMPORARY_FAILURE = "temporary_failure"
    NO_IMAGE = "no_image"
    PLACEHOLDER_IMAGE = "placeholder_image"


class ExtractionMethod(StrEnum):
    OG_IMAGE = "og_image"
    DOM_FALLBACK = "dom_fallback"


NO_RETRY_OUTCOMES = {
    LinkedInPhotoError.INVALID_URL,
    LinkedInPhotoError.NOT_FOUND,
    LinkedInPhotoError.CAPTCHA,
    LinkedInPhotoError.NO_IMAGE,
    LinkedInPhotoError.PLACEHOLDER_IMAGE,
}

ROTATE_PROFILE_OUTCOMES = {
    LinkedInPhotoError.AUTH_REQUIRED,
    LinkedInPhotoError.RATE_LIMITED,
}


@dataclass
class LinkedInPhotoResult:
    outcome: LinkedInPhotoError
    image_bytes: bytes | None = None
    content_type: str | None = None
    method: ExtractionMethod | None = None
    confidence: float = 0.0


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
    return any(fragment in lowered for fragment in placeholder_fragments())


def has_valid_linkedin_session(driver: Any) -> bool:
    """Return True when the MLX profile already has an authenticated LinkedIn session."""
    driver.get(LINKEDIN_FEED_URL)
    return detect_page_state(driver) == LinkedInPhotoError.SUCCESS


def _map_outcome_to_profile(outcome: LinkedInPhotoError) -> ProfileOutcome | None:
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


def connect_selenium(port: int) -> Any:
    """Connect a Selenium Remote driver to a Multilogin profile port."""
    from selenium import webdriver
    from selenium.webdriver.chromium.options import ChromiumOptions

    settings = get_settings()
    host = settings.multilogin_selenium_host.rstrip("/")
    options = ChromiumOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Remote(command_executor=f"{host}:{port}", options=options)
    driver.set_page_load_timeout(settings.tier1_browser_timeout_seconds)
    return driver


def login_linkedin(driver: Any) -> LinkedInPhotoError:
    """Log into LinkedIn with bot credentials when the session is not already valid."""
    settings = get_settings()
    if settings.tier1_skip_login_if_session_valid and has_valid_linkedin_session(driver):
        logger.debug("LinkedIn session already valid; skipping login")
        return LinkedInPhotoError.SUCCESS

    email = settings.linkedin_bot_email.strip()
    password = settings.linkedin_bot_password.get_secret_value().strip()
    if not email or not password:
        return LinkedInPhotoError.AUTH_REQUIRED

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    driver.get(LINKEDIN_LOGIN_URL)
    state = detect_page_state(driver)
    if state in {LinkedInPhotoError.CAPTCHA, LinkedInPhotoError.SUCCESS}:
        return state

    wait = WebDriverWait(driver, settings.tier1_browser_timeout_seconds)
    try:
        username_input = wait.until(ec.presence_of_element_located((By.ID, "username")))
        password_input = driver.find_element(By.ID, "password")
        username_input.clear()
        username_input.send_keys(email)
        password_input.clear()
        password_input.send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
    except Exception:
        logger.warning("LinkedIn login form interaction failed", exc_info=True)
        return LinkedInPhotoError.TEMPORARY_FAILURE

    return detect_page_state(driver)


def detect_page_state(driver: Any) -> LinkedInPhotoError:
    """Classify the current LinkedIn page (login wall, captcha, 404, ok)."""
    current_url = (driver.current_url or "").lower()
    page_source = (driver.page_source or "").lower()

    if "captcha" in current_url or "recaptcha" in page_source or "security verification" in page_source:
        return LinkedInPhotoError.CAPTCHA

    if any(token in current_url for token in ("/login", "/checkpoint", "/authwall", "uas/login")):
        return LinkedInPhotoError.AUTH_REQUIRED

    if "rate limit" in page_source or "too many requests" in page_source:
        return LinkedInPhotoError.RATE_LIMITED

    if any(
        token in page_source
        for token in ("page not found", "this page doesn't exist", "profile isn't available")
    ):
        return LinkedInPhotoError.NOT_FOUND

    return LinkedInPhotoError.SUCCESS


def extract_photo_url(
    driver: Any,
) -> tuple[str | None, ExtractionMethod | None, LinkedInPhotoError]:
    """Extract a profile photo URL via og:image, then guarded DOM fallback."""
    css = "css selector"

    for node in driver.find_elements(css, 'meta[property="og:image"]'):
        content = (node.get_attribute("content") or "").strip()
        if not content or is_placeholder_image_url(content):
            continue
        return content, ExtractionMethod.OG_IMAGE, LinkedInPhotoError.SUCCESS

    for selector in DOM_PHOTO_SELECTORS:
        for img in driver.find_elements(css, selector):
            for attr in ("src", "data-delayed-url", "data-ghost-url"):
                candidate = (img.get_attribute(attr) or "").strip()
                if not candidate or is_placeholder_image_url(candidate):
                    continue
                return candidate, ExtractionMethod.DOM_FALLBACK, LinkedInPhotoError.SUCCESS

    og_nodes = driver.find_elements(css, 'meta[property="og:image"]')
    if og_nodes and is_placeholder_image_url(og_nodes[0].get_attribute("content") or ""):
        return None, None, LinkedInPhotoError.PLACEHOLDER_IMAGE

    return None, None, LinkedInPhotoError.NO_IMAGE


def save_failure_screenshot(driver: Any, job_id: str | None) -> None:
    """Persist a failure screenshot for manual debugging."""
    if driver is None:
        return
    try:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = job_id or "probe"
        path = ARTIFACTS_DIR / f"{suffix}_{stamp}.png"
        driver.save_screenshot(str(path))
        logger.info("Saved Tier 1 failure screenshot to %s", path.name)
    except Exception:
        logger.warning("Failed to save Tier 1 screenshot", exc_info=True)


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


def _scrape_on_driver(driver: Any, linkedin_url: str) -> tuple[LinkedInPhotoResult, str | None]:
    """Selenium-only scrape steps once a driver is connected."""
    login_state = login_linkedin(driver)
    if login_state not in {LinkedInPhotoError.SUCCESS, LinkedInPhotoError.AUTH_REQUIRED}:
        return LinkedInPhotoResult(outcome=login_state), None

    if login_state == LinkedInPhotoError.AUTH_REQUIRED:
        return LinkedInPhotoResult(outcome=LinkedInPhotoError.AUTH_REQUIRED), None

    driver.get(linkedin_url)
    page_state = detect_page_state(driver)
    if page_state != LinkedInPhotoError.SUCCESS:
        return LinkedInPhotoResult(outcome=page_state), None

    image_url, method, extract_state = extract_photo_url(driver)
    if extract_state != LinkedInPhotoError.SUCCESS or not image_url or method is None:
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


class LinkedInBrowserClient:
    """Orchestrates Multilogin profile lifecycle and LinkedIn photo extraction."""

    def __init__(
        self,
        mlx: MultiloginClient | None = None,
        pool: ProfilePool | None = None,
    ) -> None:
        self.mlx = mlx or MultiloginClient()
        self.pool = pool or ProfilePool(self.mlx)

    async def scrape_photo(
        self,
        linkedin_url: str,
        *,
        job_id: str | None = None,
        max_profile_attempts: int = 3,
    ) -> LinkedInPhotoResult:
        """Scrape a LinkedIn profile photo with retry and profile rotation."""
        if not extract_linkedin_slug(linkedin_url):
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.INVALID_URL)

        settings = get_settings()
        if settings.browser_mode.strip().lower() != "multilogin":
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)

        async with browser_semaphore():
            last_result = LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)
            for profile_attempt in range(max_profile_attempts):
                result = await self._scrape_with_profile(
                    linkedin_url,
                    job_id=job_id,
                    same_profile_retries=2,
                )
                last_result = result
                if result.outcome == LinkedInPhotoError.SUCCESS:
                    return result
                if result.outcome in NO_RETRY_OUTCOMES:
                    return result
                if result.outcome in ROTATE_PROFILE_OUTCOMES and profile_attempt + 1 < max_profile_attempts:
                    continue
                if result.outcome == LinkedInPhotoError.TEMPORARY_FAILURE:
                    continue
                return result
            return last_result

    async def _scrape_with_profile(
        self,
        linkedin_url: str,
        *,
        job_id: str | None,
        same_profile_retries: int,
    ) -> LinkedInPhotoResult:
        profile_id: str | None = None
        driver: Any | None = None

        try:
            profile_id = await self.pool.acquire()
            token = await self.mlx.get_token()
            port = await self.mlx.start_profile(profile_id, token)
            driver = await asyncio.to_thread(connect_selenium, port)

            for attempt in range(same_profile_retries + 1):
                partial, image_url = await asyncio.to_thread(_scrape_on_driver, driver, linkedin_url)
                if partial.outcome != LinkedInPhotoError.SUCCESS:
                    if partial.outcome == LinkedInPhotoError.TEMPORARY_FAILURE and attempt < same_profile_retries:
                        continue
                    if partial.outcome != LinkedInPhotoError.SUCCESS:
                        save_failure_screenshot(driver, job_id)
                    profile_outcome = _map_outcome_to_profile(partial.outcome)
                    if profile_id and profile_outcome:
                        await self.pool.release(profile_id, profile_outcome)
                    if profile_id and partial.outcome in {
                        LinkedInPhotoError.AUTH_REQUIRED,
                        LinkedInPhotoError.CAPTCHA,
                        LinkedInPhotoError.RATE_LIMITED,
                        LinkedInPhotoError.TEMPORARY_FAILURE,
                    }:
                        await self.pool.refund_view(profile_id)
                    return partial

                image_bytes, content_type = await download_image(image_url)
                if image_bytes:
                    await self.pool.release(profile_id, ProfileOutcome.SUCCESS)
                    return LinkedInPhotoResult(
                        outcome=LinkedInPhotoError.SUCCESS,
                        image_bytes=image_bytes,
                        content_type=content_type,
                        method=partial.method,
                        confidence=partial.confidence,
                    )
                if attempt < same_profile_retries:
                    continue

            save_failure_screenshot(driver, job_id)
            await self.pool.release(profile_id, ProfileOutcome.TEMPORARY_FAILURE)
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)
        except MultiloginError:
            logger.warning("Multilogin error during LinkedIn scrape", exc_info=True)
            save_failure_screenshot(driver, job_id)
            if profile_id:
                await self.pool.release(profile_id, ProfileOutcome.TEMPORARY_FAILURE)
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)
        except Exception:
            logger.warning("LinkedIn scrape failed", exc_info=True)
            save_failure_screenshot(driver, job_id)
            if profile_id:
                await self.pool.release(profile_id, ProfileOutcome.TEMPORARY_FAILURE)
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)
        finally:
            if driver is not None:
                await asyncio.to_thread(driver.quit)
            if profile_id is not None:
                try:
                    await self.mlx.stop_profile(profile_id)
                except MultiloginError:
                    logger.warning("Failed to stop Multilogin profile after scrape", exc_info=True)


async def scrape_photo(linkedin_url: str, *, job_id: str | None = None) -> LinkedInPhotoResult:
    """Module-level helper using the default browser client."""
    return await LinkedInBrowserClient().scrape_photo(linkedin_url, job_id=job_id)
