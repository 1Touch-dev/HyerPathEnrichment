"""LinkedIn profile photo cache — Redis hot path with Postgres fallback."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from redis.exceptions import RedisError
from sqlalchemy import select

from app.config import get_settings
from app.domain.dossier import PhotoAsset
from app.storage.models import PhotoCacheRecord
from app.database.session import SessionLocal
from app.infrastructure.redis import get_redis_client

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = "tier1:photo:"


def slug_hash(slug: str) -> str:
    """Stable cache key from a normalized LinkedIn profile slug."""
    return hashlib.sha256(slug.strip().lower().encode()).hexdigest()


def _redis_key(slug: str) -> str:
    return f"{REDIS_KEY_PREFIX}{slug_hash(slug)}"


def _expires_at() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(seconds=settings.linkedin_photo_ttl_seconds)


def _record_to_photo(record: PhotoCacheRecord) -> PhotoAsset:
    confidence = 0.84 if record.extraction_method == "og_image" else 0.70
    return PhotoAsset(
        source="linkedin-photo",
        asset_url=record.asset_url,
        captured_at=record.uploaded_at,
        confidence=confidence,
    )


def _payload_from_record(record: PhotoCacheRecord) -> dict[str, str | float]:
    photo = _record_to_photo(record)
    return {
        "slug": record.slug,
        "asset_key": record.asset_key,
        "asset_url": photo.asset_url,
        "extraction_method": record.extraction_method,
        "content_hash": record.content_hash,
        "uploaded_at": photo.captured_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "source": photo.source,
        "confidence": photo.confidence,
    }


def _photo_from_payload(payload: dict) -> PhotoAsset | None:
    expires_raw = payload.get("expires_at")
    if not expires_raw:
        return None
    expires_at = datetime.fromisoformat(str(expires_raw))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return None

    uploaded_raw = payload.get("uploaded_at")
    captured_at = (
        datetime.fromisoformat(str(uploaded_raw))
        if uploaded_raw
        else datetime.now(timezone.utc)
    )
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)

    return PhotoAsset(
        source=str(payload.get("source") or "linkedin-photo"),
        asset_url=str(payload.get("asset_url") or ""),
        captured_at=captured_at,
        confidence=float(payload.get("confidence") or 0.84),
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PhotoCache:
    """Read-through cache for LinkedIn photos keyed by normalized slug."""

    async def get(self, slug: str) -> PhotoAsset | None:
        normalized = slug.strip().lower()
        if not normalized:
            return None

        cached = await self._get_from_redis(normalized)
        if cached is not None:
            return cached

        return await self._get_from_sql(normalized)

    async def put(
        self,
        slug: str,
        photo: PhotoAsset,
        *,
        asset_key: str,
        extraction_method: str,
        content_hash: str = "",
    ) -> None:
        normalized = slug.strip().lower()
        if not normalized:
            return

        now = datetime.now(timezone.utc)
        expires = _expires_at()
        record = PhotoCacheRecord(
            slug_hash=slug_hash(normalized),
            slug=normalized,
            asset_key=asset_key,
            asset_url=photo.asset_url,
            extraction_method=extraction_method,
            content_hash=content_hash,
            uploaded_at=photo.captured_at or now,
            expires_at=expires,
        )

        async with SessionLocal() as session:
            await session.merge(record)
            await session.commit()

        payload = _payload_from_record(record)
        payload["confidence"] = photo.confidence
        await self._set_redis(normalized, payload)

    async def delete(self, slug: str) -> None:
        """Remove a cached photo from Redis. SQL rows are deleted by the purge service."""
        normalized = slug.strip().lower()
        if not normalized:
            return
        try:
            await get_redis_client().delete(_redis_key(normalized))
        except RedisError:
            logger.warning("redis unavailable during photo_cache.delete")

    async def _get_from_redis(self, slug: str) -> PhotoAsset | None:
        try:
            raw = await get_redis_client().get(_redis_key(slug))
        except RedisError:
            logger.warning("redis unavailable during photo_cache.get; falling back to SQL")
            return None

        if not raw:
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None

        photo = _photo_from_payload(payload)
        if photo is not None:
            return photo
        return None

    async def _get_from_sql(self, slug: str) -> PhotoAsset | None:
        async with SessionLocal() as session:
            statement = select(PhotoCacheRecord).where(PhotoCacheRecord.slug_hash == slug_hash(slug))
            result = await session.execute(statement)
            record = result.scalar_one_or_none()

        if record is None:
            return None
        expires_at = _ensure_utc(record.expires_at)
        if expires_at <= datetime.now(timezone.utc):
            return None

        photo = _record_to_photo(record)
        payload = _payload_from_record(record) | {"confidence": photo.confidence}
        payload["expires_at"] = expires_at.isoformat()
        await self._set_redis(slug, payload)
        return photo

    async def _set_redis(self, slug: str, payload: dict[str, str | float]) -> None:
        settings = get_settings()
        try:
            await get_redis_client().set(
                _redis_key(slug),
                json.dumps(payload),
                ex=settings.linkedin_photo_ttl_seconds,
            )
        except RedisError:
            logger.warning("redis unavailable during photo_cache.put; SQL record persisted")
