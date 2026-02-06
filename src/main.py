#!/usr/bin/env python3
"""Main entry point for stock chart analysis workflow."""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .browser import BrowserManager
from .chart_capture import ChartCapture
from .claude_analysis import AnalysisResult, ClaudeAnalyzer
from .email_sender import EmailSender
from .utils import (
    get_project_root,
    load_config,
    load_env,
    load_tickers,
    setup_logging,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Daily Stock Chart Analysis Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                       # Run full workflow
  python -m src.main -t AAPL               # Analyze single ticker
  python -m src.main -t AAPL NVDA GOOG     # Analyze multiple tickers
  python -m src.main --no-email            # Skip sending email
  python -m src.main --no-headless         # Show browser window
        """,
    )

    parser.add_argument(
        "--ticker",
        "-t",
        type=str,
        nargs="+",
        help="Analyze specific ticker(s) instead of the configured list",
    )

    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip sending the email report",
    )

    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (for debugging)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Capture charts but skip Claude analysis and email",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def run_analysis(
    config: dict,
    tickers: list[dict],
    send_email: bool = True,
    dry_run: bool = False,
) -> tuple[list[AnalysisResult], dict[str, dict[str, Path]]]:
    """
    Run the chart analysis workflow.

    Args:
        config: Configuration dictionary
        tickers: List of ticker dictionaries with 'symbol' and 'name'
        send_email: Whether to send the email report
        dry_run: If True, skip Claude analysis

    Returns:
        Tuple of (results list, screenshots dict mapping symbol to {daily, weekly} paths)
    """
    logger = logging.getLogger("stockcharts")

    results: list[AnalysisResult] = []
    screenshots: dict[str, dict[str, Path]] = {}
    errors: list[tuple[str, Exception]] = []

    # Initialize components
    chart_capture = ChartCapture(config)

    if not dry_run:
        analyzer = ClaudeAnalyzer(config)

    if send_email and not dry_run:
        email_sender = EmailSender(config)

    # Process each ticker
    with BrowserManager(config) as browser:
        for ticker_info in tickers:
            symbol = ticker_info["symbol"]
            name = ticker_info.get("name", symbol)

            logger.info(f"Processing {symbol} ({name})")

            try:
                # Capture daily and weekly charts
                with browser.new_page() as page:
                    chart_paths = chart_capture.capture(page, symbol)
                    screenshots[symbol] = chart_paths

                # Analyze with Claude
                if not dry_run:
                    result = analyzer.analyze(chart_paths, symbol)
                    results.append(result)

                    # Log recommendation
                    rec = result.recommendation
                    logger.info(
                        f"{symbol}: {rec.get('signal', 'N/A')} "
                        f"(Confidence: {rec.get('confidence', 'N/A')})"
                    )

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                errors.append((symbol, e))
                continue

    # Send email report
    if send_email and not dry_run and results:
        try:
            email_sender.send_report(results, screenshots)
        except Exception as e:
            logger.error(f"Failed to send email report: {e}")
            errors.append(("email", e))

    # Summary
    logger.info(f"Completed: {len(results)} analyzed, {len(errors)} errors")

    if errors:
        logger.warning("Errors encountered:")
        for symbol, error in errors:
            logger.warning(f"  {symbol}: {error}")

    return results, screenshots


def main() -> int:
    """Main entry point."""
    # Load environment variables
    load_env()

    # Parse arguments
    args = parse_args()

    # Load configuration
    config = load_config()

    # Override headless setting if requested
    if args.no_headless:
        config.setdefault("browser", {})["headless"] = False

    # Override log level if verbose
    if args.verbose:
        config.setdefault("logging", {})["level"] = "DEBUG"

    # Setup logging
    logger = setup_logging(config)

    logger.info("=" * 60)
    logger.info(f"Stock Chart Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Get tickers to analyze
    if args.ticker:
        tickers = [{"symbol": t.upper(), "name": t.upper()} for t in args.ticker]
    else:
        tickers = load_tickers()

    if not tickers:
        logger.error("No tickers configured. Add tickers to config/tickers.yaml")
        return 1

    logger.info(f"Analyzing {len(tickers)} tickers: {', '.join(t['symbol'] for t in tickers)}")

    # Run analysis
    try:
        results, screenshots = run_analysis(
            config=config,
            tickers=tickers,
            send_email=not args.no_email,
            dry_run=args.dry_run,
        )

        # Print summary to console
        if results:
            print("\n" + "=" * 60)
            print("ANALYSIS SUMMARY")
            print("=" * 60)

            for result in results:
                rec = result.recommendation
                signal = rec.get("signal", "N/A")
                confidence = rec.get("confidence", "N/A")

                # Color codes for terminal
                colors = {"BUY": "\033[92m", "SELL": "\033[91m", "HOLD": "\033[93m"}
                reset = "\033[0m"
                color = colors.get(signal, "")

                print(f"\n{result.symbol}:")
                print(f"  Signal: {color}{signal}{reset} (Confidence: {confidence})")
                print(f"  Trend: {result.primary_trend}")
                print(f"  Summary: {result.summary[:100]}...")

            print("\n" + "=" * 60)

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
