from pathlib import Path

from app.config import get_settings

settings = get_settings()


class R2StorageClient:
    def build_asset_url(self, key: str) -> str:
        return f"{settings.r2_public_base_url.rstrip('/')}/{key.lstrip('/')}"

    async def upload_bytes(self, key: str, payload: bytes, content_type: str = "application/octet-stream") -> str:
        local_cache = Path("backend/.asset-cache")
        local_cache.mkdir(parents=True, exist_ok=True)
        (local_cache / key.replace("/", "_")).write_bytes(payload)
        return self.build_asset_url(key)
