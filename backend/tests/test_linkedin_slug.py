from __future__ import annotations

import pytest

from app.providers.linkedin_browser import extract_linkedin_slug, is_placeholder_image_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://linkedin.com/in/jane-doe", "jane-doe"),
        ("https://www.linkedin.com/in/jane-doe/", "jane-doe"),
        ("https://linkedin.com/in/jane-doe?trk=public", "jane-doe"),
        ("linkedin.com/in/jane-doe?foo=123", "jane-doe"),
        ("https://www.linkedin.com/in/Jane-Doe", "jane-doe"),
        ("https://linkedin.com/in/jane-doe/recent-activity/", "jane-doe"),
    ],
)
def test_extract_linkedin_slug_valid_profile_urls(url: str, expected: str) -> None:
    assert extract_linkedin_slug(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://linkedin.com/company/acme",
        "https://linkedin.com/school/stanford",
        "https://linkedin.com/in/",
        "https://facebook.com/in/jane-doe",
        "not-a-url",
        "https://linkedin.com/login",
        "https://linkedin.com/in/login",
    ],
)
def test_extract_linkedin_slug_rejects_invalid_urls(url: str) -> None:
    assert extract_linkedin_slug(url) is None


def test_is_placeholder_image_url_detects_defaults() -> None:
    assert is_placeholder_image_url(
        "https://static.licdn.com/aero-v1/sc/h/ghost-person.png"
    )
    assert is_placeholder_image_url("https://media.licdn.com/default-avatar.png")
    assert not is_placeholder_image_url(
        "https://media.licdn.com/dms/image/C4D03AQG/example/photo.jpg"
    )
