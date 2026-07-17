from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ASSET_CACHE_DIR = BACKEND_ROOT / ".asset-cache"

_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/png": "png",
    "image/gif": "gif",
}


class R2StorageError(Exception):
    """Raised when a configured R2 upload fails."""


def extension_for_content_type(content_type: str) -> str:
    """Map a MIME type to a file extension for object keys."""
    normalized = content_type.split(";")[0].strip().lower()
    return _CONTENT_TYPE_EXTENSIONS.get(normalized, "jpg")


def object_key_with_extension(key: str, content_type: str) -> str:
    """Ensure an object key ends with the extension implied by ``content_type``."""
    normalized_key = key.lstrip("/")
    ext = extension_for_content_type(content_type)
    if "." in Path(normalized_key).name:
        return normalized_key
    return f"{normalized_key}.{ext}"


def r2_is_configured(settings: Settings | None = None) -> bool:
    """Return True when all required Cloudflare R2 credentials are present."""
    cfg = settings or get_settings()
    return bool(
        cfg.r2_account_id.strip()
        and cfg.r2_access_key_id.strip()
        and cfg.r2_secret_access_key.get_secret_value().strip()
        and cfg.r2_bucket.strip()
    )


class R2StorageClient:
    """Upload enrichment assets to Cloudflare R2 or a local dev cache."""

    def build_asset_url(self, key: str) -> str:
        settings = get_settings()
        return f"{settings.r2_public_base_url.rstrip('/')}/{key.lstrip('/')}"

    async def upload_bytes(
        self,
        key: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        settings = get_settings()
        object_key = object_key_with_extension(key, content_type)

        if r2_is_configured(settings):
            try:
                await self._upload_to_r2(object_key, payload, content_type, settings)
                return self.build_asset_url(object_key)
            except Exception as exc:
                logger.warning("R2 upload failed; falling back to local cache", exc_info=True)
                if settings.app_env.strip().lower() == "production":
                    raise R2StorageError("R2 upload failed") from exc

        await self._upload_to_local_cache(object_key, payload)
        return self.build_asset_url(object_key)

    async def delete_object(self, key: str) -> bool:
        """Delete an object from R2 or the local dev cache. Returns True if removed."""
        settings = get_settings()
        object_key = key.lstrip("/")

        if r2_is_configured(settings):
            try:
                await self._delete_from_r2(object_key, settings)
                return True
            except Exception:
                logger.warning("R2 delete failed for key=%s; trying local cache", object_key[:32], exc_info=True)

        return self._delete_from_local_cache(object_key)

    async def _delete_from_r2(self, key: str, settings: Settings) -> None:
        try:
            import aioboto3
        except ImportError as exc:
            raise R2StorageError("aioboto3 is not installed") from exc

        endpoint = f"https://{settings.r2_account_id.strip()}.r2.cloudflarestorage.com"
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.r2_access_key_id.strip(),
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value().strip(),
            region_name="auto",
        ) as client:
            await client.delete_object(Bucket=settings.r2_bucket.strip(), Key=key)

    def _delete_from_local_cache(self, key: str) -> bool:
        destination = LOCAL_ASSET_CACHE_DIR / key.replace("/", "_")
        if destination.exists():
            destination.unlink()
            return True
        return False

    async def _upload_to_r2(
        self,
        key: str,
        payload: bytes,
        content_type: str,
        settings: Settings,
    ) -> None:
        try:
            import aioboto3
        except ImportError as exc:
            raise R2StorageError("aioboto3 is not installed") from exc

        endpoint = f"https://{settings.r2_account_id.strip()}.r2.cloudflarestorage.com"
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.r2_access_key_id.strip(),
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value().strip(),
            region_name="auto",
        ) as client:
            await client.put_object(
                Bucket=settings.r2_bucket.strip(),
                Key=key,
                Body=payload,
                ContentType=content_type,
            )
            await client.head_object(Bucket=settings.r2_bucket.strip(), Key=key)

    async def _upload_to_local_cache(self, key: str, payload: bytes) -> Path:
        LOCAL_ASSET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        destination = LOCAL_ASSET_CACHE_DIR / key.replace("/", "_")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return destination
