"""Playwright browser management."""

import logging
from contextlib import contextmanager
from typing import Generator

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

logger = logging.getLogger("stockcharts")


class BrowserManager:
    """Manages Playwright browser lifecycle."""

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

    def start(self) -> None:
        """Start the Playwright browser."""
        logger.info(f"Starting browser (headless={self.headless})")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

    def stop(self) -> None:
        """Stop the browser and cleanup."""
        if self._browser:
            logger.info("Closing browser")
            self._browser.close()
            self._browser = None

        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    @contextmanager
    def new_context(self) -> Generator[BrowserContext, None, None]:
        """
        Create a new browser context.

        Yields:
            Browser context for isolated session
        """
        if not self._browser:
            raise RuntimeError("Browser not started. Call start() first.")

        context = self._browser.new_context(
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
            context.close()

    @contextmanager
    def new_page(self) -> Generator[Page, None, None]:
        """
        Create a new page in a fresh context.

        Yields:
            Page for browser interaction
        """
        with self.new_context() as context:
            page = context.new_page()
            try:
                yield page
            finally:
                page.close()

    def __enter__(self) -> "BrowserManager":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()
