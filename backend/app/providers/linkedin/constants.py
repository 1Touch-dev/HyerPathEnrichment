"""LinkedIn browser scraping constants and DOM selectors."""

from __future__ import annotations

import re
from pathlib import Path

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"
SIGN_IN_BUTTON_XPATH = "//button[.//span[normalize-space()='Sign in']]"
LOGIN_EMAIL_SELECTOR = 'input[type="email"]'
LOGIN_PASSWORD_SELECTOR = 'input[type="password"]'
LOGIN_TYPING_PAUSE_SECONDS = 0.04
REACT_SYNC_INPUT_JS = """
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
ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "tier1"

PLACEHOLDER_SUBSTRINGS = (
    "ghost-person",
    "ghost_person",
    "default-avatar",
    "default_avatar",
    "static-exp1/static/img/person",
    "static.licdn.com/aero-v1/sc/h/",
    "/images/ghost",
    "profile-displayphoto-default",
    "blank-profile",
    "silhouette",
    "company-logo",
    "licdn.com/dms/image/c4e03aq",  # common LI placeholder hash prefix
    "data:image/gif;base64",
    "data:image/svg",
)

PLACEHOLDER_RE = re.compile(r"/0(?:[?#]|$)")

TOPCARD_PHOTO_CONTAINER_SELECTORS = (
    'div[componentkey="topcard-logo-image-referencekey"]',
    'div[aria-label="Profile photo"]',
)
FIGURE_PHOTO_SELECTOR = 'div[componentkey="topcard-logo-image-referencekey"] figure img'

DOM_PHOTO_SELECTORS = (
    FIGURE_PHOTO_SELECTOR,
    'div[componentkey="topcard-logo-image-referencekey"] img',
    'div[aria-label="Profile photo"] img',
    # Legacy LinkedIn markup still seen on some profiles / auth walls.
    "img.pv-top-card-profile-picture__image",
    'img[src*="profile-displayphoto"]',
)

DOM_PHOTO_ATTRS = ("src", "data-delayed-url", "data-ghost-url", "data-src")
