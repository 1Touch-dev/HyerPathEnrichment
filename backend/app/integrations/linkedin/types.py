"""LinkedIn photo scraping types and outcome sets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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
