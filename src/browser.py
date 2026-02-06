"""Playwright browser management with async support."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = logging.getLogger("stockcharts")


class AsyncBrowserManager:
    """Manages Playwright browser lifecycle with async support."""

    def __init__(self, config: dict):
        """
        Initialize browser manager.

        Args:
            config: Browser configuration dictionary
        """
        self.config = config.get("browser", {})
        self.headless = self.config.get("headless", True)
        self.timeout = self.config.get("timeout", 30000)
        self.viewport = self.config.get("viewport", {"width": 1920, "height": 1080})

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        """Start the Playwright browser."""
        logger.info(f"Starting browser (headless={self.headless})")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

    async def stop(self) -> None:
        """Stop the browser and cleanup."""
        if self._browser:
            logger.info("Closing browser")
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    @asynccontextmanager
    async def new_context(self) -> AsyncGenerator[BrowserContext, None]:
        """
        Create a new browser context.

        Yields:
            Browser context for isolated session
        """
        if not self._browser:
            raise RuntimeError("Browser not started. Call start() first.")

        context = await self._browser.new_context(
            viewport=self.viewport,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        context.set_default_timeout(self.timeout)

        try:
            yield context
        finally:
            await context.close()

    @asynccontextmanager
    async def new_page(self) -> AsyncGenerator[Page, None]:
        """
        Create a new page in a fresh context.

        Yields:
            Page for browser interaction
        """
        async with self.new_context() as context:
            page = await context.new_page()
            try:
                yield page
            finally:
                await page.close()

    async def __aenter__(self) -> "AsyncBrowserManager":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
