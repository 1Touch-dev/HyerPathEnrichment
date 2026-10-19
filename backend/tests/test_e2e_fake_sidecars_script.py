from typing import Any

import httpx
import pytest

from scripts import e2e_fake_sidecars as fake


class _Response:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, Any],
        *,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.cookies = httpx.Cookies(cookies)

    def json(self) -> dict[str, Any]:
        return self._payload


@pytest.mark.asyncio
async def test_fake_sidecar_probe_authenticates_via_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url: str, **kwargs: Any) -> _Response:
            assert url.endswith("/auth/login")
            assert kwargs["json"] == {
                "email": "verified@example.com",
                "password": "VerifiedPassword123",
            }
            return _Response(200, {"success": True, "data": {}}, cookies={"access_token": "jwt"})

    monkeypatch.setenv("E2E_USER_EMAIL", "verified@example.com")
    monkeypatch.setenv("E2E_USER_PASSWORD", "VerifiedPassword123")
    monkeypatch.setattr(fake.httpx, "AsyncClient", lambda **_kwargs: _Client())

    probe = fake.FakeSidecarProbe()
    assert await probe.authenticate() is True
    assert probe.headers == {"Cookie": "access_token=jwt"}
    assert probe.results[-1].name == "api_cookie_auth"
    assert probe.results[-1].ok is True


@pytest.mark.asyncio
async def test_fake_sidecar_probe_auth_fails_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("E2E_USER_EMAIL", raising=False)
    monkeypatch.delenv("E2E_USER_PASSWORD", raising=False)

    probe = fake.FakeSidecarProbe()
    assert await probe.authenticate() is False
    assert probe.headers == {}
    assert probe.results[-1].ok is False
