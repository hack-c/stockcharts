"""StockCharts.com navigation and screenshot capture."""

import logging
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .utils import get_screenshot_path, get_project_root, retry

logger = logging.getLogger("stockcharts")


class ChartCapture:
    """Captures stock charts from StockCharts.com."""

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

    def _dismiss_popups(self, page: Page) -> None:
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
                if page.locator(selector).first.is_visible(timeout=1000):
                    page.locator(selector).first.click()
                    logger.debug(f"Dismissed popup with selector: {selector}")
                    time.sleep(0.5)
            except PlaywrightTimeout:
                continue
            except Exception as e:
                logger.debug(f"Could not dismiss popup {selector}: {e}")

    def _configure_chart_type(self, page: Page) -> None:
        """Configure the chart type to candlesticks."""
        try:
            select = page.locator("#chart-type-menu-lower")
            if select.is_visible(timeout=5000):
                select.select_option(value="Candlesticks")
                logger.info("Set chart type to Candlesticks")
                time.sleep(1)
            else:
                logger.warning("Chart type selector not found")
        except Exception as e:
            logger.warning(f"Error setting chart type: {e}")

    def _set_period(self, page: Page, period: str) -> None:
        """
        Set the chart period (Daily, Weekly, etc.).

        Args:
            page: Playwright page instance
            period: Period name (e.g., "Daily", "Weekly")
        """
        try:
            # Get current chart image src to detect when it changes
            chart_img = page.locator("#chart-image")
            old_src = chart_img.get_attribute("src") if chart_img.is_visible(timeout=2000) else None

            # Click the Period dropdown button
            period_button = page.locator("#period-dropdown-menu-toggle-button")
            if period_button.is_visible(timeout=3000):
                period_button.click()
                time.sleep(1)

                # Click the desired period option (it's a button element in the dropdown)
                # Use exact text match to avoid matching e.g. "Weekly Elder Bars" when looking for "Weekly"
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
                        if option.is_visible(timeout=1000):
                            option.click()
                            logger.info(f"Set period to {period}")
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    logger.warning(f"{period} option not found in dropdown")
                    return

                # Wait for chart to update (src should change)
                if old_src:
                    for _ in range(10):  # Wait up to 5 seconds
                        time.sleep(0.5)
                        new_src = chart_img.get_attribute("src")
                        if new_src != old_src:
                            logger.info("Chart image updated after period change")
                            break
                    else:
                        logger.warning("Chart image src did not change after period selection")
                else:
                    time.sleep(2)
            else:
                logger.warning("Period dropdown button not found")
        except Exception as e:
            logger.warning(f"Error setting period: {e}")

    def _set_range(self, page: Page, range_value: str) -> None:
        """
        Set the chart range (1 Year, 5 Years, etc.).

        Args:
            page: Playwright page instance
            range_value: Range value (e.g., "1 Year", "5 Years")
        """
        try:
            # Get current chart image src to detect when it changes
            chart_img = page.locator("#chart-image")
            old_src = chart_img.get_attribute("src") if chart_img.is_visible(timeout=2000) else None

            # Click the Range dropdown button
            range_button = page.locator("#range-dropdown-menu-toggle-button")
            if range_button.is_visible(timeout=3000):
                range_button.click()
                time.sleep(1)

                # Click the desired range option (it's a button element in the dropdown)
                # Use exact text match to avoid partial matches
                option_selectors = [
                    f'button.ellipsis-overflow:text-is("{range_value}")',
                    f'button:text-is("{range_value}")',
                    f'[role="menuitem"]:text-is("{range_value}")',
                ]

                clicked = False
                for selector in option_selectors:
                    try:
                        option = page.locator(selector).first
                        if option.is_visible(timeout=1000):
                            option.click()
                            logger.info(f"Set range to {range_value}")
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    logger.warning(f"{range_value} option not found in range dropdown")
                    return

                # Wait for chart to update (src should change)
                if old_src:
                    for _ in range(10):  # Wait up to 5 seconds
                        time.sleep(0.5)
                        new_src = chart_img.get_attribute("src")
                        if new_src != old_src:
                            logger.info("Chart image updated after range change")
                            break
                    else:
                        logger.warning("Chart image src did not change after range selection")
                else:
                    time.sleep(2)
            else:
                logger.warning("Range dropdown button not found")
        except Exception as e:
            logger.warning(f"Error setting range: {e}")

    def _add_rsi_indicator(self, page: Page) -> None:
        """Add RSI indicator to the chart."""
        try:
            select = page.locator("#indicator-menu-1")
            if select.is_visible(timeout=5000):
                select.select_option(value="RSI")
                logger.info("Set indicator 1 to RSI")
                time.sleep(1)
            else:
                logger.warning("Indicator menu not found")
        except Exception as e:
            logger.warning(f"Error adding RSI indicator: {e}")

    def _click_update_button(self, page: Page) -> None:
        """Click the Update button to apply chart settings."""
        try:
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
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        logger.info("Clicked Update button")
                        time.sleep(2)
                        return
                except PlaywrightTimeout:
                    continue

            logger.debug("No Update button found, chart may auto-update")
        except Exception as e:
            logger.warning(f"Error clicking update button: {e}")

    def _wait_for_chart(self, page: Page) -> None:
        """Wait for the chart to fully render."""
        # Just wait for the chart image to be visible - don't wait for networkidle
        # as ads keep loading and cause timeouts
        time.sleep(2)
        logger.debug("Chart render wait complete")

    def _save_chart_image(self, page: Page, save_path: Path) -> bool:
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
            if chart_img.is_visible(timeout=5000):
                img_src = chart_img.get_attribute("src")
                if img_src:
                    logger.info(f"Downloading chart image from: {img_src[:80]}...")

                    # Download the image directly
                    response = page.request.get(img_src)
                    if response.ok:
                        with open(save_path, "wb") as f:
                            f.write(response.body())
                        logger.info(f"Saved chart image to {save_path}")
                        return True
                    else:
                        logger.warning(f"Failed to download image: {response.status}")
        except Exception as e:
            logger.warning(f"Error downloading chart image: {e}")

        # Fallback: screenshot the chart image element
        try:
            chart_img = page.locator("#chart-image")
            if chart_img.is_visible(timeout=2000):
                chart_img.screenshot(path=str(save_path))
                logger.info(f"Saved chart element screenshot to {save_path}")
                return True
        except Exception as e:
            logger.warning(f"Error screenshotting chart element: {e}")

        return False

    def _capture_pnf_chart(self, page: Page, symbol: str, period: str, save_path: Path) -> bool:
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

            page.goto(url, wait_until="domcontentloaded")
            time.sleep(3)

            # Get current image src before changing period
            pnf_img = page.locator('img[src*="c-sc"]').first
            old_src = None
            if pnf_img.is_visible(timeout=3000):
                old_src = pnf_img.get_attribute("src")

            # Set the period if weekly
            if period.lower() == "weekly":
                period_select = page.locator("#SCForm1-period")
                if period_select.is_visible(timeout=3000):
                    period_select.select_option(value="weekly")
                    logger.info("Set P&F period to weekly")

                    # Click the Update button to submit the form (causes page reload)
                    update_btn = page.locator("#submitButton")
                    if update_btn.is_visible(timeout=2000):
                        update_btn.click()
                        logger.info("Clicked P&F Update button")
                        # Wait for page to reload
                        time.sleep(3)

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
                    if img.is_visible(timeout=2000):
                        img_src = img.get_attribute("src")
                        if img_src:
                            # Make sure URL is absolute
                            if img_src.startswith("/"):
                                img_src = f"https://stockcharts.com{img_src}"

                            response = page.request.get(img_src)
                            if response.ok:
                                with open(save_path, "wb") as f:
                                    f.write(response.body())
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
                    if container.is_visible(timeout=1000):
                        container.screenshot(path=str(save_path))
                        logger.info(f"Saved P&F screenshot to {save_path}")
                        return True
            except Exception as e:
                logger.warning(f"Error screenshotting P&F container: {e}")

            return False

        except Exception as e:
            logger.warning(f"Error capturing P&F chart: {e}")
            return False

    @retry(max_attempts=3, delay=2.0, exceptions=(Exception,))
    def capture(self, page: Page, symbol: str) -> dict[str, Path]:
        """
        Capture daily and weekly stock chart screenshots plus P&F charts.

        Args:
            page: Playwright page instance
            symbol: Stock ticker symbol

        Returns:
            Dict with 'daily', 'weekly', 'pnf_daily', 'pnf_weekly' paths
        """
        url = f"{self.BASE_URL}?s={symbol}"
        logger.info(f"Capturing charts for {symbol}")

        # Navigate to the chart page
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(2)

        # Handle any popups
        self._dismiss_popups(page)

        # Configure chart settings (once)
        self._configure_chart_type(page)

        # Add indicators if configured
        for indicator in self.indicators:
            if indicator.get("name", "").upper() == "RSI":
                self._add_rsi_indicator(page)

        # Click Update to apply settings
        self._click_update_button(page)

        # Wait for chart to render
        self._wait_for_chart(page)

        # Dismiss any popups that appeared
        self._dismiss_popups(page)

        # Prepare paths
        screenshots_dir = get_project_root() / "output" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        # Ensure we're on Daily period and save
        self._set_period(page, "Daily")
        self._click_update_button(page)
        self._wait_for_chart(page)

        daily_path = screenshots_dir / f"{symbol}_daily.png"
        if self._save_chart_image(page, daily_path):
            result["daily"] = daily_path

        # Switch to Weekly with 5 Years range and save
        self._set_period(page, "Weekly")
        self._set_range(page, "5 Years")
        self._click_update_button(page)
        self._wait_for_chart(page)

        weekly_path = screenshots_dir / f"{symbol}_weekly.png"
        if self._save_chart_image(page, weekly_path):
            result["weekly"] = weekly_path

        # Capture Point & Figure charts
        pnf_daily_path = screenshots_dir / f"{symbol}_pnf_daily.png"
        if self._capture_pnf_chart(page, symbol, "daily", pnf_daily_path):
            result["pnf_daily"] = pnf_daily_path

        pnf_weekly_path = screenshots_dir / f"{symbol}_pnf_weekly.png"
        if self._capture_pnf_chart(page, symbol, "weekly", pnf_weekly_path):
            result["pnf_weekly"] = pnf_weekly_path

        return result
