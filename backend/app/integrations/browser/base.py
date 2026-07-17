from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BrowserProvider:
    """Provides a browser page for Tier 1 work behind a config-selected backend.

    ``BROWSER_MODE=local`` (free default) launches a local headless Chromium.
    ``multilogin`` attaches to a Multilogin profile over CDP. The caller only
    asks for ``page()`` and never learns which backend it received. Playwright
    is an optional dependency: if it (or a browser) is unavailable, ``page()``
    yields ``None`` so Tier 1 degrades to no photo instead of crashing.
    """

    def __init__(self, proxy: str | None = None) -> None:
        self.proxy = proxy

    @asynccontextmanager
    async def page(self) -> AsyncIterator[Any | None]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright not installed; Tier 1 browser unavailable")
            yield None
            return

        settings = get_settings()
        mode = settings.browser_mode.strip().lower()
        async with async_playwright() as playwright:
            browser = None
            try:
                if mode == "multilogin" and settings.multilogin_cdp_url.strip():
                    browser = await playwright.chromium.connect_over_cdp(
                        settings.multilogin_cdp_url.strip()
                    )
                else:
                    launch_kwargs: dict[str, Any] = {"headless": True}
                    if self.proxy:
                        launch_kwargs["proxy"] = {"server": self.proxy}
                    browser = await playwright.chromium.launch(**launch_kwargs)
                page = await browser.new_page()
                yield page
            except Exception:
                logger.warning("browser session failed", exc_info=True)
                yield None
            finally:
                if browser is not None:
                    await browser.close()
