from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from app.config import get_settings
from app.providers.multilogin import MultiloginClient, MultiloginError, sign_in, start_profile, stop_profile


@pytest.fixture
def mlx_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "multilogin_email", "bot@example.com")
    monkeypatch.setattr(settings, "multilogin_password", SecretStr("secret"))
    monkeypatch.setattr(settings, "multilogin_folder_id", "folder-uuid")
    monkeypatch.setattr(settings, "multilogin_workspace_id", "")
    monkeypatch.setattr(settings, "multilogin_profile_id", "")
    monkeypatch.setattr(settings, "multilogin_api_url", "https://api.multilogin.com")
    monkeypatch.setattr(
        settings,
        "multilogin_launcher_url",
        "https://launcher.mlx.yt:45001/api/v2",
    )


@pytest.mark.asyncio
async def test_sign_in_hashes_password_and_caches_token(mlx_settings: None) -> None:
    client = MultiloginClient()

    with patch("app.clients.multilogin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(
            return_value=httpx.Response(200, json={"data": {"token": "tok-123"}})
        )
        mock_client_cls.return_value = mock_client

        token = await client.sign_in(force=True)
        assert token == "tok-123"
        token2 = await client.sign_in()
        assert token2 == "tok-123"
        assert mock_client.post.await_count == 1

        payload = mock_client.post.await_args.kwargs["json"]
        assert payload["email"] == "bot@example.com"
        assert payload["password"] == hashlib.md5(b"secret").hexdigest()


@pytest.mark.asyncio
async def test_sign_in_exchanges_workspace_token(
    mlx_settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "multilogin_workspace_id", "ws-uuid")
    client = MultiloginClient()

    with patch("app.clients.multilogin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(
            side_effect=[
                httpx.Response(
                    200,
                    json={"data": {"token": "base-tok", "refresh_token": "ref-tok"}},
                ),
                httpx.Response(200, json={"data": {"token": "ws-tok"}}),
            ]
        )
        mock_client_cls.return_value = mock_client

        token = await client.sign_in(force=True)
        assert token == "ws-tok"
        assert mock_client.post.await_count == 2
        refresh_payload = mock_client.post.await_args_list[1].kwargs["json"]
        assert refresh_payload == {
            "email": "bot@example.com",
            "refresh_token": "ref-tok",
            "workspace_id": "ws-uuid",
        }
        assert "refresh_token" in str(mock_client.post.await_args_list[1].args[0])


@pytest.mark.asyncio
async def test_start_profile_returns_port(mlx_settings: None) -> None:
    client = MultiloginClient()
    client._token = "tok-123"
    client._token_expires_at = 1e12

    with patch("app.clients.multilogin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(
            return_value=httpx.Response(200, json={"data": {"port": 43210}})
        )
        mock_client_cls.return_value = mock_client

        port = await client.start_profile("profile-uuid")
        assert port == 43210
        call_kwargs = mock_client.get.await_args.kwargs
        assert call_kwargs["params"] == {"automation_type": "selenium"}
        assert "profile-uuid" in str(mock_client.get.await_args.args[0])


@pytest.mark.asyncio
async def test_stop_profile_uses_v1_launcher_path(mlx_settings: None) -> None:
    client = MultiloginClient()
    client._token = "tok-123"
    client._token_expires_at = 1e12

    with patch("app.clients.multilogin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=httpx.Response(200, json={"status": "ok"}))
        mock_client_cls.return_value = mock_client

        await client.stop_profile("profile-uuid")
        url = str(mock_client.get.await_args.args[0])
        assert "/api/v1/profile/stop/p/profile-uuid" in url


@pytest.mark.asyncio
async def test_list_profiles_filters_folder(mlx_settings: None) -> None:
    client = MultiloginClient()
    client._token = "tok-123"
    client._token_expires_at = 1e12

    with patch("app.clients.multilogin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "profiles": [{"profile_id": "p1"}, {"profile_id": "p2"}],
                        "total": 2,
                    }
                },
            )
        )
        mock_client_cls.return_value = mock_client

        ids = await client.list_profiles()
        assert ids == ["p1", "p2"]
        payload = mock_client.post.await_args.kwargs["json"]
        assert payload["search_text"] == ""
        assert payload["folder_id"] == "folder-uuid"


@pytest.mark.asyncio
async def test_list_profiles_uses_fixed_profile_id(
    mlx_settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "multilogin_profile_id", "fixed-profile-uuid")
    client = MultiloginClient()

    with patch("app.clients.multilogin.httpx.AsyncClient") as mock_client_cls:
        ids = await client.list_profiles()
        assert ids == ["fixed-profile-uuid"]
        mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_list_profiles_search_400_raises(mlx_settings: None) -> None:
    client = MultiloginClient()
    client._token = "tok-123"
    client._token_expires_at = 1e12

    with patch("app.clients.multilogin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(
            return_value=httpx.Response(400, text='{"status":{"error_code":"BAD_REQUEST"}}')
        )
        mock_client_cls.return_value = mock_client

        with pytest.raises(MultiloginError) as exc_info:
            await client.list_profiles()
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_sign_in_failure_raises(mlx_settings: None) -> None:
    with patch("app.clients.multilogin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=httpx.Response(401, json={"status": "fail"}))
        mock_client_cls.return_value = mock_client

        with pytest.raises(MultiloginError):
            await sign_in(force=True)


@pytest.mark.asyncio
async def test_module_wrappers_delegate(mlx_settings: None) -> None:
    with patch("app.clients.multilogin._default_client") as mock_default:
        mock_default.sign_in = AsyncMock(return_value="tok")
        mock_default.start_profile = AsyncMock(return_value=12345)
        mock_default.stop_profile = AsyncMock()

        assert await sign_in(force=True) == "tok"
        assert await start_profile("pid", "tok") == 12345
        await stop_profile("pid", "tok")
        mock_default.stop_profile.assert_awaited_once_with("pid", "tok")
