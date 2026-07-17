from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.dossier import PhotoAsset
from app.storage.models import PhotoCacheRecord
from app.storage.photo_cache import PhotoCache, slug_hash


class _FakeRedis:
    def __init__(self) -> None:
        self._kv: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._kv[key] = value
        return True


@pytest.fixture
async def db_session(monkeypatch: pytest.MonkeyPatch, tmp_path) -> AsyncSession:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'photo_cache.db').as_posix()}"
    from tests.migration_helpers import upgrade_head

    upgrade_head(url)
    engine = create_async_engine(url)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr("app.storage.photo_cache.SessionLocal", session_factory)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    fake = _FakeRedis()
    monkeypatch.setattr("app.storage.photo_cache.get_redis_client", lambda: fake)
    return fake


def test_slug_hash_normalizes_case() -> None:
    assert slug_hash("Jane-Doe") == slug_hash("jane-doe")


@pytest.mark.asyncio
async def test_get_miss_returns_none(fake_redis: _FakeRedis, db_session: AsyncSession) -> None:
    cache = PhotoCache()
    assert await cache.get("jane-doe") is None


@pytest.mark.asyncio
async def test_put_and_get_hit_redis(
    fake_redis: _FakeRedis,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "linkedin_photo_ttl_seconds", 3600)
    cache = PhotoCache()
    captured_at = datetime.now(timezone.utc)
    photo = PhotoAsset(
        source="linkedin-photo",
        asset_url="https://cdn.example.com/linkedin/jane-doe.jpg",
        captured_at=captured_at,
        confidence=0.84,
    )

    await cache.put(
        "jane-doe",
        photo,
        asset_key="linkedin/jane-doe.jpg",
        extraction_method="og_image",
        content_hash=hashlib.sha256(b"img").hexdigest(),
    )

    cached = await cache.get("jane-doe")
    assert cached is not None
    assert cached.asset_url == photo.asset_url
    assert cached.confidence == 0.84


@pytest.mark.asyncio
async def test_same_slug_different_url_variants_hit_cache(
    fake_redis: _FakeRedis,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "linkedin_photo_ttl_seconds", 3600)
    cache = PhotoCache()
    photo = PhotoAsset(
        source="linkedin-photo",
        asset_url="https://cdn.example.com/linkedin/jane-doe.jpg",
        captured_at=datetime.now(timezone.utc),
        confidence=0.84,
    )
    await cache.put(
        "jane-doe",
        photo,
        asset_key="linkedin/jane-doe.jpg",
        extraction_method="og_image",
    )

    cached = await cache.get("Jane-Doe")
    assert cached is not None
    assert cached.asset_url.endswith("jane-doe.jpg")


@pytest.mark.asyncio
async def test_expired_sql_record_returns_none(
    fake_redis: _FakeRedis,
    db_session: AsyncSession,
) -> None:
    cache = PhotoCache()
    expired = datetime.now(timezone.utc) - timedelta(seconds=60)
    record = PhotoCacheRecord(
        slug_hash=slug_hash("jane-doe"),
        slug="jane-doe",
        asset_key="linkedin/jane-doe.jpg",
        asset_url="https://cdn.example.com/linkedin/jane-doe.jpg",
        extraction_method="og_image",
        content_hash="abc",
        uploaded_at=expired,
        expires_at=expired,
    )
    db_session.add(record)
    await db_session.commit()

    assert await cache.get("jane-doe") is None


@pytest.mark.asyncio
async def test_sql_fallback_when_redis_empty(
    fake_redis: _FakeRedis,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "linkedin_photo_ttl_seconds", 3600)
    cache = PhotoCache()
    photo = PhotoAsset(
        source="linkedin-photo",
        asset_url="https://cdn.example.com/linkedin/jane-doe.webp",
        captured_at=datetime.now(timezone.utc),
        confidence=0.70,
    )
    await cache.put(
        "jane-doe",
        photo,
        asset_key="linkedin/jane-doe.webp",
        extraction_method="dom_fallback",
    )

    fake_redis._kv.clear()
    cached = await cache.get("jane-doe")
    assert cached is not None
    assert cached.asset_url.endswith("jane-doe.webp")
    assert cached.confidence == 0.70
