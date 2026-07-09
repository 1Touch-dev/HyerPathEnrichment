from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.providers.linkedin_browser import (
    ExtractionMethod,
    LinkedInBrowserClient,
    LinkedInPhotoError,
    detect_page_state,
    extract_photo_url,
    is_placeholder_image_url,
    login_linkedin,
    scrape_photo,
)


class _FakeElement:
    def __init__(self, attrs: dict[str, str]) -> None:
        self._attrs = attrs

    def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)


class _FakeDriver:
    def __init__(
        self,
        *,
        current_url: str = "https://www.linkedin.com/in/example",
        page_source: str = "<html></html>",
        elements: dict[str, list[_FakeElement]] | None = None,
    ) -> None:
        self.current_url = current_url
        self.page_source = page_source
        self._elements = elements or {}
        self.calls: list[str] = []

    def get(self, url: str) -> None:
        self.calls.append(url)

    def find_elements(self, _by: object, selector: str) -> list[_FakeElement]:
        return list(self._elements.get(selector, []))

    def quit(self) -> None:
        return None

    def save_screenshot(self, _path: str) -> bool:
        return True


def test_extract_photo_url_prefers_og_image() -> None:
    driver = _FakeDriver(
        elements={
            'meta[property="og:image"]': [
                _FakeElement({"content": "https://media.licdn.com/dms/image/photo.jpg"})
            ]
        }
    )
    url, method, state = extract_photo_url(driver)
    assert state == LinkedInPhotoError.SUCCESS
    assert method == ExtractionMethod.OG_IMAGE
    assert url is not None and "photo.jpg" in url


def test_extract_photo_url_skips_placeholder_og_and_uses_dom() -> None:
    driver = _FakeDriver(
        elements={
            'meta[property="og:image"]': [
                _FakeElement({"content": "https://static.licdn.com/aero-v1/sc/h/ghost-person.png"})
            ],
            "img.pv-top-card-profile-picture__image": [
                _FakeElement({"src": "https://media.licdn.com/dms/image/real.jpg"})
            ],
        }
    )
    url, method, state = extract_photo_url(driver)
    assert state == LinkedInPhotoError.SUCCESS
    assert method == ExtractionMethod.DOM_FALLBACK
    assert url is not None and "real.jpg" in url


def test_extract_photo_url_placeholder_only() -> None:
    driver = _FakeDriver(
        elements={
            'meta[property="og:image"]': [
                _FakeElement({"content": "https://static.licdn.com/default-avatar.png"})
            ]
        }
    )
    url, method, state = extract_photo_url(driver)
    assert state == LinkedInPhotoError.PLACEHOLDER_IMAGE
    assert url is None
    assert method is None


def test_detect_page_state_captcha_and_login() -> None:
    captcha_driver = _FakeDriver(
        current_url="https://www.linkedin.com/checkpoint/challenge/captcha",
        page_source="recaptcha",
    )
    assert detect_page_state(captcha_driver) == LinkedInPhotoError.CAPTCHA

    login_driver = _FakeDriver(current_url="https://www.linkedin.com/login")
    assert detect_page_state(login_driver) == LinkedInPhotoError.AUTH_REQUIRED


def test_login_linkedin_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "tier1_skip_login_if_session_valid", False)
    monkeypatch.setattr(settings, "linkedin_bot_email", "")
    monkeypatch.setattr(settings, "linkedin_bot_password", settings.linkedin_bot_password.__class__(""))

    driver = _FakeDriver(current_url="https://www.linkedin.com/login")
    assert login_linkedin(driver) == LinkedInPhotoError.AUTH_REQUIRED


@pytest.mark.asyncio
async def test_scrape_photo_invalid_url() -> None:
    result = await scrape_photo("https://linkedin.com/company/acme")
    assert result.outcome == LinkedInPhotoError.INVALID_URL
    assert result.image_bytes is None


@pytest.mark.asyncio
async def test_scrape_photo_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "browser_mode", "multilogin")

    fake_result = MagicMock()
    fake_result.outcome = LinkedInPhotoError.SUCCESS
    fake_result.image_bytes = b"img"
    fake_result.content_type = "image/jpeg"
    fake_result.method = ExtractionMethod.OG_IMAGE
    fake_result.confidence = 0.84

    with patch(
        "app.providers.linkedin_browser.LinkedInBrowserClient.scrape_photo",
        new=AsyncMock(return_value=fake_result),
    ):
        result = await scrape_photo("https://linkedin.com/in/jane-doe")
    assert result.image_bytes == b"img"
    assert result.confidence == 0.84


@pytest.mark.asyncio
async def test_browser_client_downloads_image(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "browser_mode", "multilogin")
    monkeypatch.setattr(settings, "linkedin_bot_email", "bot@example.com")
    monkeypatch.setattr(settings, "linkedin_bot_password", settings.linkedin_bot_password.__class__("secret"))

    driver = _FakeDriver(
        current_url="https://www.linkedin.com/in/jane-doe",
        elements={
            'meta[property="og:image"]': [
                _FakeElement({"content": "https://media.licdn.com/dms/image/photo.jpg"})
            ]
        },
    )

    mlx = AsyncMock()
    mlx.get_token = AsyncMock(return_value="tok")
    mlx.start_profile = AsyncMock(return_value=43210)
    mlx.stop_profile = AsyncMock()

    pool = AsyncMock()
    pool.acquire = AsyncMock(return_value="profile-1")
    pool.release = AsyncMock()

    client = LinkedInBrowserClient(mlx=mlx, pool=pool)

    with (
        patch("app.providers.linkedin_browser.browser_semaphore") as sem_mock,
        patch("app.providers.linkedin_browser.connect_selenium", return_value=driver),
        patch(
            "app.providers.linkedin_browser._scrape_on_driver",
            return_value=(
                MagicMock(
                    outcome=LinkedInPhotoError.SUCCESS,
                    method=ExtractionMethod.OG_IMAGE,
                    confidence=0.84,
                ),
                "https://media.licdn.com/dms/image/photo.jpg",
            ),
        ),
        patch("app.providers.linkedin_browser.asyncio.to_thread", side_effect=lambda fn, *args: fn(*args)),
        patch(
            "app.providers.linkedin_browser.download_image",
            new=AsyncMock(return_value=(b"jpeg-bytes", "image/jpeg")),
        ),
    ):
        sem = AsyncMock()
        sem.__aenter__ = AsyncMock(return_value=None)
        sem.__aexit__ = AsyncMock(return_value=None)
        sem_mock.return_value = sem
        result = await client.scrape_photo("https://linkedin.com/in/jane-doe", job_id="job-1")

    assert result.outcome == LinkedInPhotoError.SUCCESS
    assert result.image_bytes == b"jpeg-bytes"
    assert result.method == ExtractionMethod.OG_IMAGE
    pool.release.assert_awaited_once()
    mlx.stop_profile.assert_awaited_once_with("profile-1")
