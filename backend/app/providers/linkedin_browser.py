"""LinkedIn profile photo scraping via Selenium + Multilogin."""

from __future__ import annotations

import asyncio
import logging
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
SIGN_IN_BUTTON_XPATH = "//button[.//span[normalize-space()='Sign in']]"
LOGIN_EMAIL_SELECTOR = 'input[type="email"]'
LOGIN_PASSWORD_SELECTOR = 'input[type="password"]'
LOGIN_INPUT_INDEX = 0
LOGIN_TYPING_PAUSE_SECONDS = 0.04
_REACT_SYNC_INPUT_JS = """
const el = arguments[0];
const value = arguments[1];
const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
if (setter) {
    setter.call(el, value);
} else {
    el.value = value;
}
el.dispatchEvent(new Event('input', { bubbles: true }));
el.dispatchEvent(new Event('change', { bubbles: true }));
"""
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

TOPCARD_PHOTO_CONTAINER_SELECTORS = (
    'div[componentkey="topcard-logo-image-referencekey"]',
    'div[aria-label="Profile photo"]',
)
FIGURE_PHOTO_SELECTOR = 'div[componentkey="topcard-logo-image-referencekey"] figure img'

DOM_PHOTO_SELECTORS = (
    FIGURE_PHOTO_SELECTOR,
    'div[componentkey="topcard-logo-image-referencekey"] img',
    'div[aria-label="Profile photo"] img',
    # "img.pv-top-card-profile-picture__image--show",
    # "img.pv-top-card-profile-picture__image",
    # "img.top-card-layout__entity-image",
    # "img[data-delayed-url]",
    # "img.profile-photo-edit__preview",
    # 'img[src*="profile-displayphoto"]',
)

DOM_PHOTO_ATTRS = ("src", "data-delayed-url", "data-ghost-url", "data-src")


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


# def _find_login_input(driver: Any, wait: Any, selector: str) -> Any:
#     """Wait for and return ``querySelectorAll(selector)[LOGIN_INPUT_INDEX]``."""
#     from selenium.webdriver.common.by import By

#     def _locate(d: Any) -> Any:
#         elements = d.find_elements(By.CSS_SELECTOR, selector)
#         if len(elements) > LOGIN_INPUT_INDEX:
#             print("elements[LOGIN_INPUT_INDEX]", elements[LOGIN_INPUT_INDEX])
#             return elements[LOGIN_INPUT_INDEX]
#         return False

#     return wait.until(_locate)

def _find_login_input(driver, wait, selector):
    from selenium.webdriver.common.by import By

    def _locate(d):
        elements = d.find_elements(By.CSS_SELECTOR, selector)

        print(f"\nFound {len(elements)} elements")

        for i, e in enumerate(elements):
            print(
                i,
                "displayed=", e.is_displayed(),
                "enabled=", e.is_enabled(),
                "rect=", e.rect,
            )

        for e in elements:
            if e.is_displayed() and e.is_enabled():
                return e

        return False

    return wait.until(_locate)


def _sign_in_button_enabled(button: Any) -> bool:
    """Return True when LinkedIn's Sign in control is visible and clickable."""
    if not button.is_displayed():
        return False
    if not button.is_enabled():
        return False
    aria_disabled = (button.get_attribute("aria-disabled") or "").strip().lower()
    return aria_disabled not in {"true", "1"}


def _find_sign_in_button(driver, wait):
    from selenium.webdriver.common.by import By

    def _locate(d):
        buttons = d.find_elements(
            By.XPATH,
            "//button[.//span[normalize-space()='Sign in']]"
        )

        print("Sign in buttons found:", len(buttons))

        for b in buttons:
            print(
                "displayed:",
                b.is_displayed(),
                "enabled:",
                b.is_enabled(),
                "text:",
                b.text
            )

        if buttons:
            return buttons[0]

        return False

    return wait.until(_locate)


# def _wait_for_enabled_sign_in_button(driver: Any, wait: Any) -> Any:
    """Wait until the Sign in button exists and LinkedIn has enabled it."""

    # def _locate(d: Any) -> Any:
    #     from selenium.webdriver.common.by import By

    #     buttons = d.find_elements(By.XPATH, SIGN_IN_BUTTON_XPATH)
    #     if not buttons:
    #         buttons = d.find_elements(By.CSS_SELECTOR, "button[type='submit']")
    #     if len(buttons) <= LOGIN_INPUT_INDEX:
    #         return False
    #     button = buttons[LOGIN_INPUT_INDEX]
    #     if _sign_in_button_enabled(button):
    #         return button
    #     return False

    # return wait.until(_locate)
    def _locate(d):
        from selenium.webdriver.common.by import By

        buttons = d.find_elements(By.CSS_SELECTOR, "button[type='submit']")

        print("\nButtons found:", len(buttons))

        for i, b in enumerate(buttons):
            print(
                i,
                "displayed=", b.is_displayed(),
                "enabled=", b.is_enabled(),
                "aria-disabled=", b.get_attribute("aria-disabled"),
                "disabled=", b.get_attribute("disabled"),
                "text=", b.text,
            )

        if not buttons:
            return False

        button = buttons[0]

        if _sign_in_button_enabled(button):
            return button

        return False

def _wait_for_enabled_sign_in_button(driver, wait):
    from selenium.webdriver.common.by import By

    while True:
        buttons = driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")

        print("Buttons:", len(buttons))

        for i, b in enumerate(buttons):
            print(
                i,
                "displayed=", b.is_displayed(),
                "enabled=", b.is_enabled(),
                "aria-disabled=", b.get_attribute("aria-disabled"),
                "disabled=", b.get_attribute("disabled"),
                "text=", b.text,
            )

        input("Press Enter after inspecting the browser...")
        break

def _type_into_login_field(driver: Any, field: Any, value: str) -> None:
    """Type into a React-controlled LinkedIn login field and sync component state."""
    from selenium.webdriver.common.action_chains import ActionChains

    field.click()
    field.clear()

    actions = ActionChains(driver)
    actions.click(field)
    for char in value:
        actions.send_keys(char)
        actions.pause(LOGIN_TYPING_PAUSE_SECONDS)
    actions.perform()

    driver.execute_script(_REACT_SYNC_INPUT_JS, field, value)


def _click_sign_in_button(driver: Any, button: Any) -> None:
    """Scroll the Sign in button into view and click it, with a JS fallback."""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    try:
        button.click()
    except Exception:
        logger.debug("Sign in native click failed; using JS click", exc_info=True)
        driver.execute_script("arguments[0].click();", button)


def _wait_for_post_login_navigation(driver: Any, wait: Any) -> None:
    """Wait until LinkedIn leaves the login form or shows a challenge page."""

    def _done(d: Any) -> bool:
        url = (d.current_url or "").lower()
        if any(token in url for token in ("/checkpoint", "/authwall", "captcha")):
            return True
        return "/login" not in url and "uas/login" not in url

    wait.until(_done)


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

    from selenium.webdriver.support.ui import WebDriverWait

    driver.get(LINKEDIN_LOGIN_URL)
    print(driver.current_url)
    print(driver.title)
    print(driver.page_source[:1000])
    driver.save_screenshot("linkedin_login.png")
    state = detect_page_state(driver)
    if state in {LinkedInPhotoError.CAPTCHA, LinkedInPhotoError.SUCCESS}:
        return state

    wait = WebDriverWait(driver, settings.tier1_browser_timeout_seconds)
    try:
        from selenium.webdriver.common.keys import Keys

        email_input = _find_login_input(driver, wait, LOGIN_EMAIL_SELECTOR)
        password_input = _find_login_input(driver, wait, LOGIN_PASSWORD_SELECTOR)
        print("Email element:", email_input)
        print("Password element:", password_input)
        print(
            "Email displayed:",
            email_input.is_displayed(),
            "enabled:",
            email_input.is_enabled(),
        )
        print(
            "Password displayed:",
            password_input.is_displayed(),
            "enabled:",
            password_input.is_enabled(),
        )


        # _type_into_login_field(driver, email_input, email)
        # _type_into_login_field(driver, password_input, password)
        # password_input.send_keys(Keys.TAB)

        # sign_in_button = _wait_for_enabled_sign_in_button(driver, wait)
        _type_into_login_field(driver, email_input, email)
        _type_into_login_field(driver, password_input, password)

        password_input.send_keys(Keys.TAB)

        sign_in_button = _find_sign_in_button(driver, wait)
        print("Displayed:", sign_in_button.is_displayed())
        print("Enabled:", sign_in_button.is_enabled())
        print("Disabled:", sign_in_button.get_attribute("disabled"))
        print("aria-disabled:", sign_in_button.get_attribute("aria-disabled"))
        print("Class:", sign_in_button.get_attribute("class"))
        print(sign_in_button.text)
        _click_sign_in_button(driver, sign_in_button)
        _wait_for_post_login_navigation(driver, wait)
    except Exception:
        logger.warning("LinkedIn login form interaction failed", exc_info=True)
        return LinkedInPhotoError.TEMPORARY_FAILURE

    state = detect_page_state(driver)
    logger.debug(
        "Login finished state=%s url=%s title=%s",
        state,
        driver.current_url,
        driver.title,
    )
    return state


def detect_page_state(driver: Any) -> LinkedInPhotoError:
    """Classify the current LinkedIn page (login wall, captcha, 404, ok)."""
    current_url = (driver.current_url or "").lower()
    page_source = (driver.page_source or "").lower()

    challenge_url = any(token in current_url for token in ("/checkpoint", "/challenge", "captcha"))
    if challenge_url:
        return LinkedInPhotoError.CAPTCHA

    if any(token in current_url for token in ("/login", "/authwall", "uas/login")):
        return LinkedInPhotoError.AUTH_REQUIRED

    if "rate limit" in page_source or "too many requests" in page_source:
        return LinkedInPhotoError.RATE_LIMITED

    if any(
        token in page_source
        for token in ("page not found", "this page doesn't exist", "profile isn't available")
    ):
        return LinkedInPhotoError.NOT_FOUND

    return LinkedInPhotoError.SUCCESS


def _photo_url_from_srcset(srcset: str) -> str | None:
    """Return the first URL from an img srcset attribute."""
    for part in srcset.split(","):
        url = part.strip().split(" ", 1)[0].strip()
        if url:
            return url
    return None


def _photo_candidates_from_element(img: Any) -> list[str]:
    """Collect possible profile photo URLs from a DOM img element."""
    candidates: list[str] = []
    for attr in DOM_PHOTO_ATTRS:
        value = (img.get_attribute(attr) or "").strip()
        if value:
            candidates.append(value)
    srcset = (img.get_attribute("srcset") or "").strip()
    if srcset:
        parsed = _photo_url_from_srcset(srcset)
        if parsed:
            candidates.append(parsed)
    return candidates


def _extract_photo_from_topcard_container(driver: Any) -> str | None:
    """Extract profile photo URL from LinkedIn's stable topcard avatar container.

    The real profile photo is inside a <figure> tag. Suggested/related profiles
    also have images in the topcard but they are NOT inside a <figure>.
    """
    from selenium.webdriver.common.by import By

    for img in driver.find_elements(By.CSS_SELECTOR, FIGURE_PHOTO_SELECTOR):
        for candidate in _photo_candidates_from_element(img):
            if candidate and not is_placeholder_image_url(candidate):
                return candidate

    for container_sel in TOPCARD_PHOTO_CONTAINER_SELECTORS:
        for container in driver.find_elements(By.CSS_SELECTOR, container_sel):
            for img in container.find_elements(By.TAG_NAME, "img"):
                for candidate in _photo_candidates_from_element(img):
                    if candidate and not is_placeholder_image_url(candidate):
                        return candidate
    return None


def _has_topcard_photo_img(driver: Any) -> bool:
    """Return True when the real topcard profile photo (inside <figure>) is present."""
    from selenium.webdriver.common.by import By

    css = "css selector"

    if driver.find_elements(css, FIGURE_PHOTO_SELECTOR):
        return True

    for composite in (
        'div[componentkey="topcard-logo-image-referencekey"] img',
        'div[aria-label="Profile photo"] img',
    ):
        if driver.find_elements(css, composite):
            return True

    for container_sel in TOPCARD_PHOTO_CONTAINER_SELECTORS:
        for container in driver.find_elements(By.CSS_SELECTOR, container_sel):
            if container.find_elements(By.TAG_NAME, "img"):
                return True
    return False


def _log_photo_extraction_debug(driver: Any) -> None:
    """Log DOM probes when profile photo extraction fails."""
    css = "css selector"
    og_nodes = driver.find_elements(css, 'meta[property="og:image"]')
    og_content = (og_nodes[0].get_attribute("content") or "").strip() if og_nodes else ""
    logger.warning(
        "Photo extraction debug og:image_count=%s og_content=%r placeholder=%s",
        len(og_nodes),
        og_content[:200] if og_content else "",
        is_placeholder_image_url(og_content) if og_content else None,
    )

    from selenium.webdriver.common.by import By

    for container_sel in TOPCARD_PHOTO_CONTAINER_SELECTORS:
        containers = driver.find_elements(By.CSS_SELECTOR, container_sel)
        if not containers:
            continue

        figures = containers[0].find_elements(By.TAG_NAME, "figure")
        logger.warning(
            "Photo extraction debug topcard container=%r count=%s figure_count=%s",
            container_sel,
            len(containers),
            len(figures),
        )

        imgs = containers[0].find_elements(By.TAG_NAME, "img")
        attrs = {}
        if imgs:
            attrs = {
                attr: (imgs[0].get_attribute(attr) or "").strip()
                for attr in (*DOM_PHOTO_ATTRS, "srcset")
            }
        logger.warning(
            "Photo extraction debug topcard container=%r count=%s img_count=%s attrs=%s",
            container_sel,
            len(containers),
            len(imgs),
            attrs,
        )

    for selector in DOM_PHOTO_SELECTORS:
        imgs = driver.find_elements(css, selector)
        if not imgs:
            continue
        first = imgs[0]
        attrs = {
            attr: (first.get_attribute(attr) or "").strip()
            for attr in (*DOM_PHOTO_ATTRS, "srcset")
        }
        logger.warning(
            "Photo extraction debug selector=%r count=%s attrs=%s",
            selector,
            len(imgs),
            attrs,
        )

    profile_imgs = driver.find_elements(css, 'img[src*="profile-displayphoto"]')
    if profile_imgs:
        first_src = (profile_imgs[0].get_attribute("src") or "").strip()
        logger.warning(
            "Photo extraction debug profile-displayphoto count=%s src=%r placeholder=%s",
            len(profile_imgs),
            first_src[:200] if first_src else "",
            is_placeholder_image_url(first_src) if first_src else None,
        )


def _wait_for_profile_photo_ready(driver: Any, wait: Any) -> None:
    """Wait until og:image or the real profile photo img (inside figure) is present."""

    def _ready(_d: Any) -> bool:
        css = "css selector"

        for node in _d.find_elements(css, 'meta[property="og:image"]'):
            if (node.get_attribute("content") or "").strip():
                return True

        if _d.find_elements(css, FIGURE_PHOTO_SELECTOR):
            return True

        for selector in DOM_PHOTO_SELECTORS:
            if _d.find_elements(css, selector):
                return True

        return bool(_d.find_elements(css, 'img[src*="profile-displayphoto"]'))

    wait.until(_ready)


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

    topcard_url = _extract_photo_from_topcard_container(driver)
    if topcard_url:
        return topcard_url, ExtractionMethod.DOM_FALLBACK, LinkedInPhotoError.SUCCESS

    for selector in DOM_PHOTO_SELECTORS:
        for img in driver.find_elements(css, selector):
            for candidate in _photo_candidates_from_element(img):
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

    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, settings.tier1_browser_timeout_seconds)
    try:
        _wait_for_profile_photo_ready(driver, wait)
    except Exception:
        logger.warning("Timed out waiting for profile photo DOM", exc_info=True)

    image_url, method, extract_state = extract_photo_url(driver)
    if extract_state != LinkedInPhotoError.SUCCESS or not image_url or method is None:
        if extract_state in {LinkedInPhotoError.NO_IMAGE, LinkedInPhotoError.PLACEHOLDER_IMAGE}:
            _log_photo_extraction_debug(driver)
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
