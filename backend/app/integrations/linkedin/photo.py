"""LinkedIn profile photo DOM extraction."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from selenium.webdriver.common.by import By

from app.integrations.linkedin.constants import (
    ARTIFACTS_DIR,
    DOM_PHOTO_ATTRS,
    DOM_PHOTO_SELECTORS,
    FIGURE_PHOTO_SELECTOR,
    TOPCARD_PHOTO_CONTAINER_SELECTORS,
)
from app.integrations.linkedin.types import ExtractionMethod, LinkedInPhotoError
from app.integrations.linkedin.urls import (
    first_valid_photo_url,
    is_placeholder_image_url,
    photo_url_from_srcset,
)

logger = logging.getLogger(__name__)


def photo_candidates_from_element(img: Any) -> list[str]:
    candidates: list[str] = []
    srcset = (img.get_attribute("srcset") or "").strip()
    if srcset:
        parsed = photo_url_from_srcset(srcset)
        if parsed:
            candidates.append(parsed)
    for attr in DOM_PHOTO_ATTRS:
        value = (img.get_attribute(attr) or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def extract_photo_from_topcard_container(driver: Any) -> str | None:
    """Extract profile photo URL from LinkedIn's stable topcard avatar container.

    The real profile photo is inside a <figure> tag. Suggested/related profiles
    also have images in the topcard but they are NOT inside a <figure>.
    """
    for img in driver.find_elements(By.CSS_SELECTOR, FIGURE_PHOTO_SELECTOR):
        url = first_valid_photo_url(photo_candidates_from_element(img))
        if url:
            return url

    for container_sel in TOPCARD_PHOTO_CONTAINER_SELECTORS:
        for container in driver.find_elements(By.CSS_SELECTOR, container_sel):
            for img in container.find_elements(By.TAG_NAME, "img"):
                url = first_valid_photo_url(photo_candidates_from_element(img))
                if url:
                    return url
    return None


def img_attrs_for_debug(img: Any) -> dict[str, str]:
    return {
        attr: (img.get_attribute(attr) or "").strip()
        for attr in (*DOM_PHOTO_ATTRS, "srcset")
    }


def log_photo_extraction_debug(driver: Any) -> None:
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
        logger.warning(
            "Photo extraction debug topcard container=%r count=%s img_count=%s attrs=%s",
            container_sel,
            len(containers),
            len(imgs),
            img_attrs_for_debug(imgs[0]) if imgs else {},
        )

    for selector in DOM_PHOTO_SELECTORS:
        imgs = driver.find_elements(css, selector)
        if not imgs:
            continue
        logger.warning(
            "Photo extraction debug selector=%r count=%s attrs=%s",
            selector,
            len(imgs),
            img_attrs_for_debug(imgs[0]),
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


def wait_for_profile_photo_ready(driver: Any, wait: Any) -> None:
    """Wait until og:image or the real profile photo img (inside figure) is present."""

    def _ready(_d: Any) -> bool:
        css = "css selector"

        for node in _d.find_elements(css, 'meta[property="og:image"]'):
            if (node.get_attribute("content") or "").strip():
                return True

        if _d.find_elements(css, FIGURE_PHOTO_SELECTOR):
            return True

        # The stable topcard avatar container indicates the browser has rendered
        # the profile photo section even when the inner <img> isn't directly matched
        # by our selectors (unit tests cover this path).
        for container_sel in TOPCARD_PHOTO_CONTAINER_SELECTORS:
            if _d.find_elements(css, container_sel):
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

    topcard_url = extract_photo_from_topcard_container(driver)
    if topcard_url:
        return topcard_url, ExtractionMethod.DOM_FALLBACK, LinkedInPhotoError.SUCCESS

    for selector in DOM_PHOTO_SELECTORS:
        for img in driver.find_elements(css, selector):
            url = first_valid_photo_url(photo_candidates_from_element(img))
            if url:
                return url, ExtractionMethod.DOM_FALLBACK, LinkedInPhotoError.SUCCESS

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
