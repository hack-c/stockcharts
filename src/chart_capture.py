"""StockCharts.com navigation and screenshot capture with async support."""

import asyncio
import logging
from pathlib import Path

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .browser import AsyncBrowserManager
from .utils import get_project_root, async_retry

logger = logging.getLogger("stockcharts")


class ChartCapture:
    """Captures stock charts from StockCharts.com using async operations."""

    BASE_URL = "https://stockcharts.com/h-sc/ui"
    PNF_URL = "https://stockcharts.com/freecharts/pnf.php"

    def __init__(self, config: dict):
        """
        Initialize chart capture.

        Args:
            config: Chart configuration dictionary
        """
        self.chart_config = config.get("chart", {})
        self.chart_type = self.chart_config.get("type", "candlestick")
        self.period = self.chart_config.get("period", "9 months")
        self.indicators = self.chart_config.get("indicators", [])

    async def _dismiss_popups(self, page: Page) -> None:
        """Dismiss any popup modals or ads."""
        popup_selectors = [
            'button:has-text("Close")',
            'button:has-text("No thanks")',
            'button:has-text("Maybe later")',
            ".modal-close",
            '[aria-label="Close"]',
            ".popup-close",
        ]

        for selector in popup_selectors:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=500):
                    await locator.click()
                    logger.debug(f"Dismissed popup with selector: {selector}")
                    await asyncio.sleep(0.2)
            except PlaywrightTimeout:
                continue
            except Exception as e:
                logger.debug(f"Could not dismiss popup {selector}: {e}")

    async def _configure_chart_type(self, page: Page) -> None:
        """Configure the chart type to candlesticks."""
        try:
            select = page.locator("#chart-type-menu-lower")
            if await select.is_visible(timeout=5000):
                await select.select_option(value="Candlesticks")
                logger.info("Set chart type to Candlesticks")
                # Wait for chart to update instead of sleeping
                try:
                    await page.wait_for_load_state("networkidle", timeout=3000)
                except PlaywrightTimeout:
                    pass  # Network may not go idle due to ads
            else:
                logger.warning("Chart type selector not found")
        except Exception as e:
            logger.warning(f"Error setting chart type: {e}")

    async def _wait_for_chart_update(self, page: Page, old_src: str, timeout: int = 10000) -> bool:
        """
        Wait for chart image src to change, indicating update complete.

        Args:
            page: Playwright page instance
            old_src: Previous src attribute value
            timeout: Maximum wait time in milliseconds

        Returns:
            True if chart updated, False if timed out
        """
        try:
            # Escape quotes in old_src for JavaScript
            escaped_src = old_src.replace("'", "\\'").replace('"', '\\"')
            await page.wait_for_function(
                f'''() => {{
                    const img = document.querySelector("#chart-image");
                    return img && img.src !== "{escaped_src}";
                }}''',
                timeout=timeout
            )
            logger.debug("Chart image updated")
            return True
        except PlaywrightTimeout:
            logger.debug("Chart update detection timed out")
            return False

    async def _set_period(self, page: Page, period: str) -> None:
        """
        Set the chart period (Daily, Weekly, etc.).

        Args:
            page: Playwright page instance
            period: Period name (e.g., "Daily", "Weekly")
        """
        try:
            # Get current chart image src to detect when it changes
            chart_img = page.locator("#chart-image")
            old_src = None
            if await chart_img.is_visible(timeout=2000):
                old_src = await chart_img.get_attribute("src")

            # Click the Period dropdown button
            period_button = page.locator("#period-dropdown-menu-toggle-button")
            if await period_button.is_visible(timeout=3000):
                await period_button.click()

                # Wait for dropdown menu to appear
                await page.wait_for_selector('button.ellipsis-overflow', timeout=2000)

                # Click the desired period option
                option_selectors = [
                    f'button.ellipsis-overflow:text-is("{period}")',
                    f'button:text-is("{period}")',
                    f'[role="menuitem"]:text-is("{period}")',
                    f'li:text-is("{period}")',
                ]

                clicked = False
                for selector in option_selectors:
                    try:
                        option = page.locator(selector).first
                        if await option.is_visible(timeout=500):
                            await option.click()
                            logger.info(f"Set period to {period}")
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    logger.warning(f"{period} option not found in dropdown")
                    return

                # Wait for chart to update
                if old_src:
                    if not await self._wait_for_chart_update(page, old_src, timeout=5000):
                        logger.warning("Chart image src did not change after period selection")
                        await page.wait_for_timeout(1000)
                else:
                    await page.wait_for_timeout(1000)
            else:
                logger.warning("Period dropdown button not found")
        except Exception as e:
            logger.warning(f"Error setting period: {e}")

    async def _set_range(self, page: Page, range_value: str) -> None:
        """
        Set the chart range (1 Year, 5 Years, etc.).

        Args:
            page: Playwright page instance
            range_value: Range value (e.g., "1 Year", "5 Years")
        """
        try:
            # Get current chart image src to detect when it changes
            chart_img = page.locator("#chart-image")
            old_src = None
            if await chart_img.is_visible(timeout=2000):
                old_src = await chart_img.get_attribute("src")

            # Click the Range dropdown button
            range_button = page.locator("#range-dropdown-menu-toggle-button")
            if await range_button.is_visible(timeout=3000):
                await range_button.click()

                # Wait for dropdown menu to appear
                await page.wait_for_selector('button.ellipsis-overflow', timeout=2000)

                # Click the desired range option
                option_selectors = [
                    f'button.ellipsis-overflow:text-is("{range_value}")',
                    f'button:text-is("{range_value}")',
                    f'[role="menuitem"]:text-is("{range_value}")',
                ]

                clicked = False
                for selector in option_selectors:
                    try:
                        option = page.locator(selector).first
                        if await option.is_visible(timeout=500):
                            await option.click()
                            logger.info(f"Set range to {range_value}")
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    logger.warning(f"{range_value} option not found in range dropdown")
                    return

                # Wait for chart to update
                if old_src:
                    if not await self._wait_for_chart_update(page, old_src, timeout=5000):
                        logger.warning("Chart image src did not change after range selection")
                        await page.wait_for_timeout(1000)
                else:
                    await page.wait_for_timeout(1000)
            else:
                logger.warning("Range dropdown button not found")
        except Exception as e:
            logger.warning(f"Error setting range: {e}")

    async def _add_rsi_indicator(self, page: Page) -> None:
        """Add RSI indicator to the chart."""
        try:
            select = page.locator("#indicator-menu-1")
            if await select.is_visible(timeout=5000):
                await select.select_option(value="RSI")
                logger.info("Set indicator 1 to RSI")
                try:
                    await page.wait_for_load_state("networkidle", timeout=3000)
                except PlaywrightTimeout:
                    pass
            else:
                logger.warning("Indicator menu not found")
        except Exception as e:
            logger.warning(f"Error adding RSI indicator: {e}")

    async def _click_update_button(self, page: Page) -> None:
        """Click the Update button to apply chart settings."""
        try:
            # Get current chart src before clicking
            chart_img = page.locator("#chart-image")
            old_src = None
            if await chart_img.is_visible(timeout=2000):
                old_src = await chart_img.get_attribute("src")

            # Look for Update button
            update_selectors = [
                'button:has-text("Update")',
                '#update-button',
                'input[value="Update"]',
                'button.update-btn',
            ]

            for selector in update_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        logger.info("Clicked Update button")

                        # Wait for chart to update
                        if old_src:
                            await self._wait_for_chart_update(page, old_src, timeout=5000)
                        else:
                            await page.wait_for_timeout(1000)
                        return
                except PlaywrightTimeout:
                    continue

            logger.debug("No Update button found, chart may auto-update")
        except Exception as e:
            logger.warning(f"Error clicking update button: {e}")

    async def _wait_for_chart(self, page: Page) -> None:
        """Wait for the chart to fully render."""
        try:
            await page.locator("#chart-image").wait_for(state="visible", timeout=5000)
            logger.debug("Chart render wait complete")
        except PlaywrightTimeout:
            logger.warning("Timeout waiting for chart to render")

    async def _save_chart_image(self, page: Page, save_path: Path) -> bool:
        """
        Save the current chart image.

        Args:
            page: Playwright page instance
            save_path: Path to save the image

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the chart image element and its src URL
            chart_img = page.locator("#chart-image")
            if await chart_img.is_visible(timeout=5000):
                img_src = await chart_img.get_attribute("src")
                if img_src:
                    logger.info(f"Downloading chart image from: {img_src[:80]}...")

                    # Download the image directly
                    response = await page.request.get(img_src)
                    if response.ok:
                        body = await response.body()
                        with open(save_path, "wb") as f:
                            f.write(body)
                        logger.info(f"Saved chart image to {save_path}")
                        return True
                    else:
                        logger.warning(f"Failed to download image: {response.status}")
        except Exception as e:
            logger.warning(f"Error downloading chart image: {e}")

        # Fallback: screenshot the chart image element
        try:
            chart_img = page.locator("#chart-image")
            if await chart_img.is_visible(timeout=2000):
                await chart_img.screenshot(path=str(save_path))
                logger.info(f"Saved chart element screenshot to {save_path}")
                return True
        except Exception as e:
            logger.warning(f"Error screenshotting chart element: {e}")

        return False

    async def _capture_pnf_chart(self, page: Page, symbol: str, period: str, save_path: Path) -> bool:
        """
        Capture a Point & Figure chart.

        Args:
            page: Playwright page instance
            symbol: Stock ticker symbol
            period: "daily" or "weekly"
            save_path: Path to save the image

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.PNF_URL}?c={symbol},P"
            logger.info(f"Capturing P&F {period} chart for {symbol}")

            await page.goto(url, wait_until="domcontentloaded")

            # Wait for P&F chart image to load
            await page.locator('img[src*="c-sc"]').first.wait_for(state="visible", timeout=5000)

            # Set the period if weekly
            if period.lower() == "weekly":
                period_select = page.locator("#SCForm1-period")
                if await period_select.is_visible(timeout=3000):
                    await period_select.select_option(value="weekly")
                    logger.info("Set P&F period to weekly")

                    # Click the Update button to submit the form
                    update_btn = page.locator("#submitButton")
                    if await update_btn.is_visible(timeout=2000):
                        await update_btn.click()
                        logger.info("Clicked P&F Update button")
                        # Wait for page to reload
                        await page.wait_for_load_state("load", timeout=10000)

            # Find and save the P&F chart image
            pnf_selectors = [
                'img[src*="c-sc"]',
                'img[src*="pnf"]',
                '#pnfChart',
                '.pnf-chart img',
                'img[alt*="Point"]',
            ]

            for selector in pnf_selectors:
                try:
                    img = page.locator(selector).first
                    if await img.is_visible(timeout=2000):
                        img_src = await img.get_attribute("src")
                        if img_src:
                            # Make sure URL is absolute
                            if img_src.startswith("/"):
                                img_src = f"https://stockcharts.com{img_src}"

                            response = await page.request.get(img_src)
                            if response.ok:
                                body = await response.body()
                                with open(save_path, "wb") as f:
                                    f.write(body)
                                logger.info(f"Saved P&F chart to {save_path}")
                                return True
                except Exception:
                    continue

            # Fallback: screenshot the main content area
            try:
                container_selectors = [
                    '#chartContainer',
                    '.chart-container',
                    '#pnfChartContainer',
                    'table img',
                ]
                for selector in container_selectors:
                    container = page.locator(selector).first
                    if await container.is_visible(timeout=1000):
                        await container.screenshot(path=str(save_path))
                        logger.info(f"Saved P&F screenshot to {save_path}")
                        return True
            except Exception as e:
                logger.warning(f"Error screenshotting P&F container: {e}")

            return False

        except Exception as e:
            logger.warning(f"Error capturing P&F chart: {e}")
            return False

    async def _capture_candlestick_charts(self, page: Page, symbol: str) -> dict[str, Path]:
        """
        Capture daily and weekly candlestick charts.

        Args:
            page: Playwright page instance
            symbol: Stock ticker symbol

        Returns:
            Dict with 'daily' and 'weekly' paths
        """
        url = f"{self.BASE_URL}?s={symbol}"
        logger.info(f"Capturing candlestick charts for {symbol}")

        # Navigate to the chart page
        await page.goto(url, wait_until="domcontentloaded")

        # Wait for chart to appear
        await page.wait_for_selector("#chart-image", timeout=10000)

        # Handle any popups
        await self._dismiss_popups(page)

        # Configure chart settings (once)
        await self._configure_chart_type(page)

        # Add indicators if configured
        for indicator in self.indicators:
            if indicator.get("name", "").upper() == "RSI":
                await self._add_rsi_indicator(page)

        # Click Update to apply settings
        await self._click_update_button(page)

        # Wait for chart to render
        await self._wait_for_chart(page)

        # Dismiss any popups that appeared
        await self._dismiss_popups(page)

        # Prepare paths
        screenshots_dir = get_project_root() / "output" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        # Ensure we're on Daily period and save
        await self._set_period(page, "Daily")
        await self._click_update_button(page)
        await self._wait_for_chart(page)

        daily_path = screenshots_dir / f"{symbol}_daily.png"
        if await self._save_chart_image(page, daily_path):
            result["daily"] = daily_path

        # Switch to Weekly with 5 Years range and save
        await self._set_period(page, "Weekly")
        await self._set_range(page, "5 Years")
        await self._click_update_button(page)
        await self._wait_for_chart(page)

        weekly_path = screenshots_dir / f"{symbol}_weekly.png"
        if await self._save_chart_image(page, weekly_path):
            result["weekly"] = weekly_path

        return result

    async def _capture_pnf_charts(self, page: Page, symbol: str) -> dict[str, Path]:
        """
        Capture daily and weekly P&F charts.

        Args:
            page: Playwright page instance
            symbol: Stock ticker symbol

        Returns:
            Dict with 'pnf_daily' and 'pnf_weekly' paths
        """
        screenshots_dir = get_project_root() / "output" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        # Capture P&F daily
        pnf_daily_path = screenshots_dir / f"{symbol}_pnf_daily.png"
        if await self._capture_pnf_chart(page, symbol, "daily", pnf_daily_path):
            result["pnf_daily"] = pnf_daily_path

        # Capture P&F weekly
        pnf_weekly_path = screenshots_dir / f"{symbol}_pnf_weekly.png"
        if await self._capture_pnf_chart(page, symbol, "weekly", pnf_weekly_path):
            result["pnf_weekly"] = pnf_weekly_path

        return result

    @async_retry(max_attempts=3, delay=2.0, exceptions=(Exception,))
    async def capture(self, browser: AsyncBrowserManager, symbol: str) -> dict[str, Path]:
        """
        Capture all 4 charts for a symbol using parallel page instances.

        Args:
            browser: AsyncBrowserManager instance
            symbol: Stock ticker symbol

        Returns:
            Dict with 'daily', 'weekly', 'pnf_daily', 'pnf_weekly' paths
        """
        logger.info(f"Capturing all charts for {symbol}")

        async def capture_candlestick():
            async with browser.new_page() as page:
                return await self._capture_candlestick_charts(page, symbol)

        async def capture_pnf():
            async with browser.new_page() as page:
                return await self._capture_pnf_charts(page, symbol)

        # Run candlestick and P&F captures in parallel
        results = await asyncio.gather(
            capture_candlestick(),
            capture_pnf(),
            return_exceptions=True
        )

        # Merge results
        merged = {}
        for r in results:
            if isinstance(r, dict):
                merged.update(r)
            elif isinstance(r, Exception):
                logger.error(f"Chart capture error for {symbol}: {r}")

        return merged
