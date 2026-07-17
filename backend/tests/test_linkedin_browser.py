from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.linkedin.browser_facade import (
    ExtractionMethod,
    LinkedInBrowserClient,
    LinkedInPhotoError,
    _find_login_input,
    _photo_url_from_srcset,
    _sign_in_button_enabled,
    _type_into_login_field,
    _wait_for_enabled_sign_in_button,
    _wait_for_profile_photo_ready,
    detect_page_state,
    extract_photo_url,
    login_linkedin,
    scrape_photo,
)


class _FakeElement:
    def __init__(
        self,
        attrs: dict[str, str],
        *,
        displayed: bool = True,
        enabled: bool = True,
        children: dict[str, list[_FakeElement]] | None = None,
    ) -> None:
        self._attrs = attrs
        self._displayed = displayed
        self._enabled = enabled
        self._children = children or {}
        self.typed: list[str] = []

    def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)

    def is_displayed(self) -> bool:
        return self._displayed

    def is_enabled(self) -> bool:
        return self._enabled

    def click(self) -> None:
        return None

    def clear(self) -> None:
        self.typed.clear()

    def send_keys(self, value: str) -> None:
        self.typed.append(value)

    def find_elements(self, by: object, selector: str) -> list[_FakeElement]:
        from selenium.webdriver.common.by import By

        if by == By.TAG_NAME:
            return list(self._children.get(selector, []))
        return list(self._children.get(selector, []))


class _FakeDriver:
    def __init__(
        self,
        *,
        current_url: str = "https://www.linkedin.com/in/example",
        page_source: str = "<html></html>",
        elements: dict[str, list[_FakeElement]] | None = None,
        xpath_elements: dict[str, list[_FakeElement]] | None = None,
    ) -> None:
        self.current_url = current_url
        self.page_source = page_source
        self._elements = elements or {}
        self._xpath_elements = xpath_elements or {}
        self.calls: list[str] = []
        self.script_calls: list[tuple[str, tuple[object, ...]]] = []

    def get(self, url: str) -> None:
        self.calls.append(url)

    def find_elements(self, by: object, selector: str) -> list[_FakeElement]:
        from selenium.webdriver.common.by import By

        if by == By.XPATH:
            return list(self._xpath_elements.get(selector, []))
        return list(self._elements.get(selector, []))

    def execute_script(self, script: str, *args: object) -> None:
        self.script_calls.append((script, args))

    def quit(self) -> None:
        return None

    def save_screenshot(self, _path: str) -> bool:
        return True


def test_photo_url_from_srcset_picks_highest_width() -> None:
    srcset = (
        "https://media.licdn.com/dms/image/photo-100.jpg 100w, "
        "https://media.licdn.com/dms/image/photo-200.jpg 200w, "
        "https://media.licdn.com/dms/image/photo-800.jpg 800w"
    )
    assert _photo_url_from_srcset(srcset) == "https://media.licdn.com/dms/image/photo-800.jpg"


def test_photo_url_from_srcset_falls_back_to_first_url() -> None:
    srcset = "https://media.licdn.com/dms/image/photo-only.jpg"
    assert _photo_url_from_srcset(srcset) == "https://media.licdn.com/dms/image/photo-only.jpg"


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


def test_extract_photo_url_profile_displayphoto_selector() -> None:
    driver = _FakeDriver(
        elements={
            'img[src*="profile-displayphoto"]': [
                _FakeElement(
                    {"src": "https://media.licdn.com/dms/image/profile-displayphoto-shrink_200_200/photo.jpg"}
                )
            ]
        }
    )
    url, method, state = extract_photo_url(driver)
    assert state == LinkedInPhotoError.SUCCESS
    assert method == ExtractionMethod.DOM_FALLBACK
    assert url is not None and "profile-displayphoto" in url


def test_extract_photo_url_uses_data_src_and_srcset() -> None:
    driver = _FakeDriver(
        elements={
            "img.pv-top-card-profile-picture__image": [
                _FakeElement(
                    {
                        "data-src": "https://media.licdn.com/dms/image/real-from-data-src.jpg",
                        "srcset": "https://media.licdn.com/dms/image/real-from-srcset.jpg 1x",
                    }
                )
            ]
        }
    )
    url, method, state = extract_photo_url(driver)
    assert state == LinkedInPhotoError.SUCCESS
    assert method == ExtractionMethod.DOM_FALLBACK
    assert url is not None and "real-from-data-src.jpg" in url


def test_extract_photo_url_prefers_topcard_componentkey() -> None:
    avatar_img = _FakeElement(
        {
            "src": "https://media.licdn.com/dms/image/profile-displayphoto-shrink_200_200/avatar.jpg"
        }
    )
    container = _FakeElement(
        {"componentkey": "topcard-logo-image-referencekey"},
        children={"img": [avatar_img]},
    )
    driver = _FakeDriver(
        elements={
            'div[componentkey="topcard-logo-image-referencekey"]': [container],
            'img[src*="profile-displayphoto"]': [
                _FakeElement(
                    {"src": "https://media.licdn.com/dms/image/profile-displayphoto-shrink_100_100/decoy.jpg"}
                )
            ],
        }
    )
    url, method, state = extract_photo_url(driver)
    assert state == LinkedInPhotoError.SUCCESS
    assert method == ExtractionMethod.DOM_FALLBACK
    assert url is not None and "avatar.jpg" in url


def test_extract_photo_url_topcard_aria_label_fallback() -> None:
    avatar_img = _FakeElement(
        {"src": "https://media.licdn.com/dms/image/profile-displayphoto-shrink_200_200/aria-avatar.jpg"}
    )
    container = _FakeElement(
        {"aria-label": "Profile photo"},
        children={"img": [avatar_img]},
    )
    driver = _FakeDriver(
        elements={
            'div[aria-label="Profile photo"]': [container],
        }
    )
    url, method, state = extract_photo_url(driver)
    assert state == LinkedInPhotoError.SUCCESS
    assert method == ExtractionMethod.DOM_FALLBACK
    assert url is not None and "aria-avatar.jpg" in url


def test_wait_for_profile_photo_ready_succeeds() -> None:
    driver = _FakeDriver(
        elements={
            'meta[property="og:image"]': [
                _FakeElement({"content": "https://media.licdn.com/dms/image/photo.jpg"})
            ]
        }
    )
    _wait_for_profile_photo_ready(driver, _FakeWait(driver))


def test_wait_for_profile_photo_ready_topcard_container() -> None:
    avatar_img = _FakeElement({"src": "https://media.licdn.com/dms/image/photo.jpg"})
    container = _FakeElement(
        {"componentkey": "topcard-logo-image-referencekey"},
        children={"img": [avatar_img]},
    )
    driver = _FakeDriver(
        elements={
            'div[componentkey="topcard-logo-image-referencekey"]': [container],
        }
    )
    _wait_for_profile_photo_ready(driver, _FakeWait(driver))


def test_detect_page_state_captcha_and_login() -> None:
    captcha_driver = _FakeDriver(
        current_url="https://www.linkedin.com/checkpoint/challenge/captcha",
        page_source="recaptcha",
    )
    assert detect_page_state(captcha_driver) == LinkedInPhotoError.CAPTCHA

    login_driver = _FakeDriver(current_url="https://www.linkedin.com/login")
    assert detect_page_state(login_driver) == LinkedInPhotoError.AUTH_REQUIRED

    feed_driver = _FakeDriver(
        current_url="https://www.linkedin.com/feed/",
        page_source="<html>...recaptcha...</html>",
    )
    assert detect_page_state(feed_driver) == LinkedInPhotoError.SUCCESS

    profile_driver = _FakeDriver(
        current_url="https://www.linkedin.com/in/narendramodi/",
        page_source="<html>...recaptcha...</html>",
    )
    assert detect_page_state(profile_driver) == LinkedInPhotoError.SUCCESS


class _FakeWait:
    def __init__(self, driver: _FakeDriver) -> None:
        self._driver = driver

    def until(self, condition: object) -> object:
        result = condition(self._driver)  # type: ignore[operator]
        assert result is not False
        return result


def test_find_login_input_uses_node_list_zero_for_email() -> None:
    driver = _FakeDriver(
        elements={
            'input[type="email"]': [
                _FakeElement({"name": "session_key"}),
                _FakeElement({"name": "decoy"}),
            ]
        }
    )
    found = _find_login_input(driver, _FakeWait(driver), 'input[type="email"]')
    assert found is not None
    assert found.get_attribute("name") == "session_key"


def test_find_login_input_uses_node_list_zero_for_password() -> None:
    driver = _FakeDriver(
        elements={
            'input[type="password"]': [
                _FakeElement({"name": "session_password"}),
                _FakeElement({"name": "decoy"}),
            ]
        }
    )
    found = _find_login_input(driver, _FakeWait(driver), 'input[type="password"]')
    assert found.get_attribute("name") == "session_password"


def test_sign_in_button_enabled_respects_disabled_and_aria() -> None:
    assert _sign_in_button_enabled(_FakeElement({}))
    assert not _sign_in_button_enabled(_FakeElement({}, enabled=False))
    assert not _sign_in_button_enabled(_FakeElement({"aria-disabled": "true"}))
    assert not _sign_in_button_enabled(_FakeElement({}, displayed=False))


def test_wait_for_enabled_sign_in_button_returns_enabled_button() -> None:
    enabled = _FakeElement({"type": "submit"})
    driver = _FakeDriver(
        xpath_elements={
            "//button[.//span[normalize-space()='Sign in']]": [enabled],
        }
    )
    found = _wait_for_enabled_sign_in_button(driver, _FakeWait(driver))
    assert found is enabled


def test_type_into_login_field_runs_react_sync_script() -> None:
    field = _FakeElement({"name": "session_key"})
    driver = _FakeDriver()

    with patch("app.integrations.linkedin.login.ActionChains") as chains_cls:
        chains = MagicMock()
        chains.click.return_value = chains
        chains.send_keys.return_value = chains
        chains.pause.return_value = chains
        chains_cls.return_value = chains

        _type_into_login_field(driver, field, "bot@example.com")

    chains.perform.assert_called_once()
    assert driver.script_calls
    assert "HTMLInputElement.prototype" in driver.script_calls[0][0]
    assert driver.script_calls[0][1][1] == "bot@example.com"


def test_login_linkedin_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

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
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "browser_mode", "multilogin")

    fake_result = MagicMock()
    fake_result.outcome = LinkedInPhotoError.SUCCESS
    fake_result.image_bytes = b"img"
    fake_result.content_type = "image/jpeg"
    fake_result.method = ExtractionMethod.OG_IMAGE
    fake_result.confidence = 0.84

    with patch(
        "app.integrations.linkedin.browser_facade.LinkedInBrowserClient.scrape_photo",
        new=AsyncMock(return_value=fake_result),
    ):
        result = await scrape_photo("https://linkedin.com/in/jane-doe")
    assert result.image_bytes == b"img"
    assert result.confidence == 0.84


@pytest.mark.asyncio
async def test_browser_client_downloads_image(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

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
        patch("app.integrations.linkedin.client.browser_semaphore") as sem_mock,
        patch("app.integrations.linkedin.client.connect_selenium", return_value=driver),
        patch(
            "app.integrations.linkedin.client.scrape_on_driver",
            return_value=(
                MagicMock(
                    outcome=LinkedInPhotoError.SUCCESS,
                    method=ExtractionMethod.OG_IMAGE,
                    confidence=0.84,
                ),
                "https://media.licdn.com/dms/image/photo.jpg",
            ),
        ),
        patch("app.integrations.linkedin.client.asyncio.to_thread", side_effect=lambda fn, *args: fn(*args)),
        patch(
            "app.integrations.linkedin.client.download_image",
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
