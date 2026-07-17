"""Multilogin profile rotation with daily view limits and cooldowns."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from enum import StrEnum

from app.config import get_settings
from app.observability.tier1_metrics import tier1_profile_pool_exhausted_total, tier1_profile_views_total
from app.clients.multilogin import MultiloginClient, MultiloginError
from app.infrastructure.redis import get_redis_client

logger = logging.getLogger(__name__)

_BROWSER_SEMAPHORE: asyncio.Semaphore | None = None
_PROFILE_LIST_CACHE: list[str] = []
_PROFILE_LIST_CACHE_AT: float = 0.0
_PROFILE_LIST_CACHE_TTL_SECONDS = 300.0


class ProfileOutcome(StrEnum):
    SUCCESS = "success"
    CAPTCHA = "captcha"
    AUTH_REQUIRED = "auth_required"
    RATE_LIMITED = "rate_limited"
    TEMPORARY_FAILURE = "temporary_failure"
    INVALID_URL = "invalid_url"
    NOT_FOUND = "not_found"


class ProfilePool:
    """Round-robin Multilogin profiles with Redis-backed limits."""

    def __init__(self, mlx: MultiloginClient | None = None) -> None:
        self.mlx = mlx or MultiloginClient()
        self._rr_index = 0

    @staticmethod
    def _views_key(profile_id: str) -> str:
        return f"tier1:profile:{profile_id}:views:{date.today().isoformat()}"

    @staticmethod
    def _cooldown_key(profile_id: str) -> str:
        return f"tier1:profile:{profile_id}:cooldown"

    async def _profile_ids(self) -> list[str]:
        global _PROFILE_LIST_CACHE, _PROFILE_LIST_CACHE_AT

        import time

        now = time.monotonic()
        if _PROFILE_LIST_CACHE and (now - _PROFILE_LIST_CACHE_AT) < _PROFILE_LIST_CACHE_TTL_SECONDS:
            return list(_PROFILE_LIST_CACHE)

        profile_ids = await self.mlx.list_profiles()
        _PROFILE_LIST_CACHE = list(profile_ids)
        _PROFILE_LIST_CACHE_AT = now
        return profile_ids

    async def _is_eligible(self, profile_id: str) -> bool:
        settings = get_settings()
        redis = get_redis_client()

        try:
            if await redis.exists(self._cooldown_key(profile_id)):
                return False
            views_raw = await redis.get(self._views_key(profile_id))
            views = int(views_raw or 0)
            return views < settings.multilogin_daily_view_limit
        except Exception:
            logger.warning("Redis unavailable for profile pool; allowing profile", exc_info=True)
            return True

    async def acquire(self) -> str:
        """Acquire the next eligible Multilogin profile id."""
        profile_ids = await self._profile_ids()
        if not profile_ids:
            raise MultiloginError("No Multilogin profiles available in configured folder")

        attempts = len(profile_ids)
        for _ in range(attempts):
            profile_id = profile_ids[self._rr_index % len(profile_ids)]
            self._rr_index = (self._rr_index + 1) % len(profile_ids)
            if await self._is_eligible(profile_id):
                redis = get_redis_client()
                try:
                    key = self._views_key(profile_id)
                    views = await redis.incr(key)
                    if views == 1:
                        await redis.expire(key, 86_400)
                    tier1_profile_views_total.labels(profile_id=profile_id).inc()
                except Exception:
                    logger.warning("Failed to increment profile view counter", exc_info=True)
                return profile_id

        tier1_profile_pool_exhausted_total.inc()
        raise MultiloginError("All Multilogin profiles are in cooldown or over daily view limit")

    async def refund_view(self, profile_id: str) -> None:
        """Refund a daily view when login/scrape failed before a real profile visit."""
        redis = get_redis_client()
        try:
            views = await redis.decr(self._views_key(profile_id))
            if views < 0:
                await redis.set(self._views_key(profile_id), 0, ex=86_400)
        except Exception:
            logger.warning("Failed to refund profile view counter", exc_info=True)

    async def release(self, profile_id: str, outcome: ProfileOutcome) -> None:
        """Record profile outcome; apply cooldown for hard failures."""
        settings = get_settings()
        redis = get_redis_client()
        cooldown_seconds: int | None = None
        if outcome in {ProfileOutcome.CAPTCHA, ProfileOutcome.AUTH_REQUIRED}:
            cooldown_seconds = settings.multilogin_profile_cooldown_seconds
        elif outcome == ProfileOutcome.RATE_LIMITED:
            cooldown_seconds = settings.multilogin_rate_limit_cooldown_seconds

        if cooldown_seconds is None:
            return

        try:
            await redis.set(self._cooldown_key(profile_id), outcome.value, ex=cooldown_seconds)
        except Exception:
            logger.warning("Failed to set profile cooldown", exc_info=True)

    async def pool_status(self) -> list[dict[str, int | str | bool]]:
        """Return per-profile view counts and cooldown state for ops/debug."""
        settings = get_settings()
        redis = get_redis_client()
        rows: list[dict[str, int | str | bool]] = []
        for profile_id in await self._profile_ids():
            views = 0
            in_cooldown = False
            try:
                views = int(await redis.get(self._views_key(profile_id)) or 0)
                in_cooldown = bool(await redis.exists(self._cooldown_key(profile_id)))
            except Exception:
                logger.warning("Redis unavailable during pool_status", exc_info=True)
            rows.append(
                {
                    "profile_id": profile_id,
                    "views_today": views,
                    "daily_limit": settings.multilogin_daily_view_limit,
                    "in_cooldown": in_cooldown,
                    "eligible": views < settings.multilogin_daily_view_limit and not in_cooldown,
                }
            )
        return rows


def browser_semaphore() -> asyncio.Semaphore:
    """Lazy global semaphore limiting concurrent Tier 1 browser sessions."""
    global _BROWSER_SEMAPHORE
    if _BROWSER_SEMAPHORE is None:
        settings = get_settings()
        limit = max(1, settings.tier1_max_concurrent_browsers)
        _BROWSER_SEMAPHORE = asyncio.Semaphore(limit)
    return _BROWSER_SEMAPHORE
