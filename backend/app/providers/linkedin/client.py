"""Multilogin-backed LinkedIn photo scraping client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_settings
from app.providers.linkedin.login import connect_selenium
from app.providers.linkedin.photo import save_failure_screenshot
from app.providers.linkedin.scrape import download_image, map_outcome_to_profile, scrape_on_driver
from app.providers.linkedin.types import (
    NO_RETRY_OUTCOMES,
    ROTATE_PROFILE_OUTCOMES,
    LinkedInPhotoError,
    LinkedInPhotoResult,
)
from app.providers.linkedin.urls import extract_linkedin_slug
from app.providers.multilogin import MultiloginClient, MultiloginError
from app.providers.profile_pool import ProfileOutcome, ProfilePool, browser_semaphore

logger = logging.getLogger(__name__)


class LinkedInBrowserClient:
    """Orchestrates Multilogin profile lifecycle and LinkedIn photo extraction."""

    def __init__(
        self,
        mlx: MultiloginClient | None = None,
        pool: ProfilePool | None = None,
    ) -> None:
        self.mlx = mlx or MultiloginClient()
        self.pool = pool or ProfilePool(self.mlx)

    async def scrape_photo(
        self,
        linkedin_url: str,
        *,
        job_id: str | None = None,
        max_profile_attempts: int = 3,
    ) -> LinkedInPhotoResult:
        """Scrape a LinkedIn profile photo with retry and profile rotation."""
        if not extract_linkedin_slug(linkedin_url):
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.INVALID_URL)

        settings = get_settings()
        if settings.browser_mode.strip().lower() != "multilogin":
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)

        async with browser_semaphore():
            last_result = LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)
            for profile_attempt in range(max_profile_attempts):
                result = await self._scrape_with_profile(
                    linkedin_url,
                    job_id=job_id,
                    same_profile_retries=2,
                )
                last_result = result
                if result.outcome == LinkedInPhotoError.SUCCESS:
                    return result
                if result.outcome in NO_RETRY_OUTCOMES:
                    return result
                if result.outcome in ROTATE_PROFILE_OUTCOMES and profile_attempt + 1 < max_profile_attempts:
                    continue
                if result.outcome == LinkedInPhotoError.TEMPORARY_FAILURE:
                    continue
                return result
            return last_result

    async def _scrape_with_profile(
        self,
        linkedin_url: str,
        *,
        job_id: str | None,
        same_profile_retries: int,
    ) -> LinkedInPhotoResult:
        profile_id: str | None = None
        driver: Any | None = None

        try:
            profile_id = await self.pool.acquire()
            token = await self.mlx.get_token()
            port = await self.mlx.start_profile(profile_id, token)
            driver = await asyncio.to_thread(connect_selenium, port)

            for attempt in range(same_profile_retries + 1):
                partial, image_url = await asyncio.to_thread(scrape_on_driver, driver, linkedin_url)
                if partial.outcome != LinkedInPhotoError.SUCCESS:
                    if partial.outcome == LinkedInPhotoError.TEMPORARY_FAILURE and attempt < same_profile_retries:
                        continue
                    if partial.outcome != LinkedInPhotoError.SUCCESS:
                        save_failure_screenshot(driver, job_id)
                    profile_outcome = map_outcome_to_profile(partial.outcome)
                    if profile_id and profile_outcome:
                        await self.pool.release(profile_id, profile_outcome)
                    if profile_id and partial.outcome in {
                        LinkedInPhotoError.AUTH_REQUIRED,
                        LinkedInPhotoError.CAPTCHA,
                        LinkedInPhotoError.RATE_LIMITED,
                        LinkedInPhotoError.TEMPORARY_FAILURE,
                    }:
                        await self.pool.refund_view(profile_id)
                    return partial

                image_bytes, content_type = await download_image(image_url)
                if image_bytes:
                    await self.pool.release(profile_id, ProfileOutcome.SUCCESS)
                    return LinkedInPhotoResult(
                        outcome=LinkedInPhotoError.SUCCESS,
                        image_bytes=image_bytes,
                        content_type=content_type,
                        method=partial.method,
                        confidence=partial.confidence,
                    )
                if attempt < same_profile_retries:
                    continue

            save_failure_screenshot(driver, job_id)
            await self.pool.release(profile_id, ProfileOutcome.TEMPORARY_FAILURE)
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)
        except MultiloginError:
            logger.warning("Multilogin error during LinkedIn scrape", exc_info=True)
            save_failure_screenshot(driver, job_id)
            if profile_id:
                await self.pool.release(profile_id, ProfileOutcome.TEMPORARY_FAILURE)
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)
        except Exception:
            logger.warning("LinkedIn scrape failed", exc_info=True)
            save_failure_screenshot(driver, job_id)
            if profile_id:
                await self.pool.release(profile_id, ProfileOutcome.TEMPORARY_FAILURE)
            return LinkedInPhotoResult(outcome=LinkedInPhotoError.TEMPORARY_FAILURE)
        finally:
            if driver is not None:
                await asyncio.to_thread(driver.quit)
            if profile_id is not None:
                try:
                    await self.mlx.stop_profile(profile_id)
                except MultiloginError:
                    logger.warning("Failed to stop Multilogin profile after scrape", exc_info=True)


async def scrape_photo(linkedin_url: str, *, job_id: str | None = None) -> LinkedInPhotoResult:
    """Module-level helper using the default browser client."""
    return await LinkedInBrowserClient().scrape_photo(linkedin_url, job_id=job_id)
