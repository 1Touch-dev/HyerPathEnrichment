from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.config import get_settings
from app.storage.r2 import (
    LOCAL_ASSET_CACHE_DIR,
    R2StorageClient,
    R2StorageError,
    extension_for_content_type,
    object_key_with_extension,
    r2_is_configured,
)


@pytest.fixture
def storage_client() -> R2StorageClient:
    return R2StorageClient()


def test_extension_for_content_type() -> None:
    assert extension_for_content_type("image/jpeg") == "jpg"
    assert extension_for_content_type("image/webp; charset=binary") == "webp"
    assert extension_for_content_type("application/octet-stream") == "jpg"


def test_object_key_with_extension_appends_when_missing() -> None:
    assert object_key_with_extension("linkedin/jane-doe", "image/webp") == "linkedin/jane-doe.webp"
    assert object_key_with_extension("linkedin/jane-doe.jpg", "image/jpeg") == "linkedin/jane-doe.jpg"


def test_r2_is_configured_requires_all_credentials() -> None:
    settings = get_settings()
    assert r2_is_configured(settings) is False

    configured = settings.model_copy(
        update={
            "r2_account_id": "acct",
            "r2_access_key_id": "key",
            "r2_secret_access_key": SecretStr("secret"),
            "r2_bucket": "bucket",
        }
    )
    assert r2_is_configured(configured) is True


@pytest.mark.asyncio
async def test_upload_bytes_writes_local_cache_without_r2(
    storage_client: R2StorageClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "asset-cache"
    monkeypatch.setattr("app.storage.r2.LOCAL_ASSET_CACHE_DIR", cache_dir)
    monkeypatch.setattr(get_settings(), "r2_account_id", "")

    url = await storage_client.upload_bytes(
        "linkedin/jane-doe",
        b"photo-bytes",
        content_type="image/jpeg",
    )

    expected_file = cache_dir / "linkedin_jane-doe.jpg"
    assert expected_file.is_file()
    assert expected_file.read_bytes() == b"photo-bytes"
    assert url.endswith("linkedin/jane-doe.jpg")


@pytest.mark.asyncio
async def test_upload_bytes_uses_r2_when_configured(
    storage_client: R2StorageClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "r2_account_id", "acct123")
    monkeypatch.setattr(settings, "r2_access_key_id", "access")
    monkeypatch.setattr(settings, "r2_secret_access_key", SecretStr("secret"))
    monkeypatch.setattr(settings, "r2_bucket", "hyrepath-assets")
    monkeypatch.setattr(settings, "r2_public_base_url", "https://cdn.example.com")

    mock_client = AsyncMock()
    mock_client.put_object = AsyncMock()
    mock_client.head_object = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client.return_value = mock_client

    fake_aioboto3 = MagicMock()
    fake_aioboto3.Session.return_value = mock_session

    with patch.dict(sys.modules, {"aioboto3": fake_aioboto3}):
        url = await storage_client.upload_bytes(
            "linkedin/jane-doe",
            b"photo-bytes",
            content_type="image/webp",
        )

    assert url == "https://cdn.example.com/linkedin/jane-doe.webp"
    mock_client.put_object.assert_awaited_once()
    put_kwargs = mock_client.put_object.await_args.kwargs
    assert put_kwargs["Bucket"] == "hyrepath-assets"
    assert put_kwargs["Key"] == "linkedin/jane-doe.webp"
    assert put_kwargs["Body"] == b"photo-bytes"
    assert put_kwargs["ContentType"] == "image/webp"
    mock_client.head_object.assert_awaited_once_with(
        Bucket="hyrepath-assets",
        Key="linkedin/jane-doe.webp",
    )


@pytest.mark.asyncio
async def test_upload_bytes_raises_in_production_when_r2_fails(
    storage_client: R2StorageClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "r2_account_id", "acct123")
    monkeypatch.setattr(settings, "r2_access_key_id", "access")
    monkeypatch.setattr(settings, "r2_secret_access_key", SecretStr("secret"))
    monkeypatch.setattr(settings, "r2_bucket", "hyrepath-assets")

    with (
        patch("app.storage.r2.r2_is_configured", return_value=True),
        patch.object(storage_client, "_upload_to_r2", side_effect=RuntimeError("network")),
        pytest.raises(R2StorageError),
    ):
        await storage_client.upload_bytes("linkedin/jane-doe", b"x", content_type="image/jpeg")


def test_local_cache_dir_is_backend_relative() -> None:
    assert LOCAL_ASSET_CACHE_DIR.name == ".asset-cache"
    assert LOCAL_ASSET_CACHE_DIR.parent.name == "backend"
