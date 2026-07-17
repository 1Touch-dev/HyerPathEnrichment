from __future__ import annotations

import pytest

from app.providers.linkedin_browser import (
    LinkedInPhotoError,
    has_valid_linkedin_session,
    is_placeholder_image_url,
    login_linkedin,
    placeholder_fragments,
)
from app.providers.profile_pool import ProfileOutcome, ProfilePool


class _FakeDriver:
    def __init__(self, *, current_url: str = "https://www.linkedin.com/feed/", page_source: str = "") -> None:
        self.current_url = current_url
        self.page_source = page_source
        self.calls: list[str] = []

    def get(self, url: str) -> None:
        self.calls.append(url)
        if "feed" in url:
            self.current_url = "https://www.linkedin.com/feed/"

    def find_elements(self, *_args: object) -> list[object]:
        return []


def test_placeholder_fragments_includes_env_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "tier1_placeholder_denylist", "custom-placeholder,Another")
    fragments = placeholder_fragments()
    assert "custom-placeholder" in fragments
    assert "another" in fragments


def test_is_placeholder_detects_company_logo() -> None:
    assert is_placeholder_image_url("https://media.licdn.com/company-logo/123.png")


def test_has_valid_linkedin_session_on_feed() -> None:
    driver = _FakeDriver()
    assert has_valid_linkedin_session(driver) is True
    assert driver.calls[0].endswith("/feed/")


def test_login_skips_form_when_session_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "tier1_skip_login_if_session_valid", True)
    monkeypatch.setattr(settings, "linkedin_bot_email", "")
    driver = _FakeDriver()
    assert login_linkedin(driver) == LinkedInPhotoError.SUCCESS
    assert all("login" not in call for call in driver.calls)


@pytest.mark.asyncio
async def test_profile_pool_refund_view(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRedis:
        def __init__(self) -> None:
            self._kv: dict[str, int] = {}

        async def exists(self, _key: str) -> bool:
            return False

        async def get(self, key: str) -> str | None:
            return str(self._kv[key]) if key in self._kv else None

        async def incr(self, key: str) -> int:
            self._kv[key] = self._kv.get(key, 0) + 1
            return self._kv[key]

        async def decr(self, key: str) -> int:
            self._kv[key] = self._kv.get(key, 0) - 1
            return self._kv[key]

        async def set(self, key: str, value: int, ex: int | None = None) -> bool:
            self._kv[key] = value
            return True

        async def expire(self, _key: str, _seconds: int) -> bool:
            return True

    fake = _FakeRedis()
    monkeypatch.setattr("app.integrations.multilogin.profile_pool.get_redis_client", lambda: fake)

    async def _fake_profile_ids(_self: ProfilePool) -> list[str]:
        return ["profile-1"]

    monkeypatch.setattr(ProfilePool, "_profile_ids", _fake_profile_ids)

    pool = ProfilePool()
    profile_id = await pool.acquire()
    assert profile_id == "profile-1"
    await pool.refund_view(profile_id)
    status = await pool.pool_status()
    assert status[0]["views_today"] == 0


@pytest.mark.asyncio
async def test_profile_release_rate_limit_uses_shorter_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    captured: dict[str, int] = {}

    class _FakeRedis:
        async def set(self, key: str, value: str, ex: int | None = None) -> bool:
            captured["ex"] = ex or 0
            return True

    monkeypatch.setattr(get_settings(), "multilogin_rate_limit_cooldown_seconds", 1800)
    monkeypatch.setattr("app.integrations.multilogin.profile_pool.get_redis_client", lambda: _FakeRedis())

    pool = ProfilePool()
    await pool.release("profile-1", ProfileOutcome.RATE_LIMITED)
    assert captured["ex"] == 1800
