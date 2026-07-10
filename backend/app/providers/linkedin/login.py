"""LinkedIn login and session detection via Selenium."""

from __future__ import annotations

import logging
from typing import Any

from selenium import webdriver
from selenium.webdriver.chromium.options import ChromiumOptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from app.config import get_settings

from app.providers.linkedin.constants import (
    LINKEDIN_FEED_URL,
    LINKEDIN_LOGIN_URL,
    LOGIN_EMAIL_SELECTOR,
    LOGIN_PASSWORD_SELECTOR,
    LOGIN_TYPING_PAUSE_SECONDS,
    REACT_SYNC_INPUT_JS,
    SIGN_IN_BUTTON_XPATH,
)
from app.providers.linkedin.types import LinkedInPhotoError

logger = logging.getLogger(__name__)


def detect_page_state(driver: Any) -> LinkedInPhotoError:
    """Classify the current LinkedIn page (login wall, captcha, 404, ok)."""
    current_url = (driver.current_url or "").lower()
    page_source = (driver.page_source or "").lower()

    if any(token in current_url for token in ("/checkpoint", "/challenge", "captcha")):
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


def has_valid_linkedin_session(driver: Any) -> bool:
    """Return True when the MLX profile already has an authenticated LinkedIn session."""
    driver.get(LINKEDIN_FEED_URL)
    return detect_page_state(driver) == LinkedInPhotoError.SUCCESS


def find_visible_enabled_input(driver: Any, wait: Any, selector: str) -> Any:
    def _locate(d: Any) -> Any:
        for element in d.find_elements(By.CSS_SELECTOR, selector):
            if element.is_displayed() and element.is_enabled():
                return element
        return False

    return wait.until(_locate)


def find_login_input(driver: Any, wait: Any, selector: str) -> Any:
    return find_visible_enabled_input(driver, wait, selector)


def sign_in_button_enabled(button: Any) -> bool:
    """Return True when LinkedIn's Sign in control is visible and clickable."""
    if not button.is_displayed():
        return False
    if not button.is_enabled():
        return False
    aria_disabled = (button.get_attribute("aria-disabled") or "").strip().lower()
    return aria_disabled not in {"true", "1"}


def find_sign_in_button(driver: Any, wait: Any) -> Any:
    def _locate(d: Any) -> Any:
        buttons = d.find_elements(By.XPATH, SIGN_IN_BUTTON_XPATH)
        if buttons:
            return buttons[0]
        return False

    return wait.until(_locate)


def wait_for_enabled_sign_in_button(driver: Any, wait: Any) -> Any:
    """Wait until the Sign in button exists and LinkedIn has enabled it."""

    def _locate(d: Any) -> Any:
        for button in d.find_elements(By.XPATH, SIGN_IN_BUTTON_XPATH):
            if sign_in_button_enabled(button):
                return button
        return False

    return wait.until(_locate)


def type_into_login_field(driver: Any, field: Any, value: str) -> None:
    """Type into a React-controlled LinkedIn login field and sync component state."""
    field.click()
    field.clear()

    actions = ActionChains(driver)
    actions.click(field)
    for char in value:
        actions.send_keys(char)
        actions.pause(LOGIN_TYPING_PAUSE_SECONDS)
    actions.perform()

    driver.execute_script(REACT_SYNC_INPUT_JS, field, value)


def click_sign_in_button(driver: Any, button: Any) -> None:
    """Scroll the Sign in button into view and click it, with a JS fallback."""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    try:
        button.click()
    except Exception:
        logger.debug("Sign in native click failed; using JS click", exc_info=True)
        driver.execute_script("arguments[0].click();", button)


def wait_for_post_login_navigation(driver: Any, wait: Any) -> None:
    """Wait until LinkedIn leaves the login form or shows a challenge page."""

    def _done(d: Any) -> bool:
        url = (d.current_url or "").lower()
        if any(token in url for token in ("/checkpoint", "/authwall", "captcha")):
            return True
        return "/login" not in url and "uas/login" not in url

    wait.until(_done)


def connect_selenium(port: int) -> Any:
    """Connect a Selenium Remote driver to a Multilogin profile port."""
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

    driver.get(LINKEDIN_LOGIN_URL)
    logger.debug("Login page loaded url=%s title=%s", driver.current_url, driver.title)
    state = detect_page_state(driver)
    if state in {LinkedInPhotoError.CAPTCHA, LinkedInPhotoError.SUCCESS}:
        return state

    wait = WebDriverWait(driver, settings.tier1_browser_timeout_seconds)
    try:
        email_input = find_login_input(driver, wait, LOGIN_EMAIL_SELECTOR)
        password_input = find_login_input(driver, wait, LOGIN_PASSWORD_SELECTOR)
        type_into_login_field(driver, email_input, email)
        type_into_login_field(driver, password_input, password)
        password_input.send_keys(Keys.TAB)
        sign_in_button = find_sign_in_button(driver, wait)
        click_sign_in_button(driver, sign_in_button)
        wait_for_post_login_navigation(driver, wait)
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
