#!/usr/bin/env python3
"""Main entry point for stock chart analysis workflow with parallel processing."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from .browser import AsyncBrowserManager
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

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent ticker processing (default: 3)",
    )

    return parser.parse_args()


async def run_analysis_async(
    config: dict,
    tickers: list[dict],
    send_email: bool = True,
    dry_run: bool = False,
    max_concurrent_tickers: int = 3,
) -> tuple[list[AnalysisResult], dict[str, dict[str, Path]]]:
    """
    Run the chart analysis workflow with parallel processing.

    Args:
        config: Configuration dictionary
        tickers: List of ticker dictionaries with 'symbol' and 'name'
        send_email: Whether to send the email report
        dry_run: If True, skip Claude analysis
        max_concurrent_tickers: Maximum tickers to process concurrently

    Returns:
        Tuple of (results list, screenshots dict mapping symbol to chart paths)
    """
    logger = logging.getLogger("stockcharts")

    screenshots: dict[str, dict[str, Path]] = {}
    errors: list[tuple[str, Exception]] = []

    # Initialize components
    chart_capture = ChartCapture(config)
    analyzer = ClaudeAnalyzer(config) if not dry_run else None

    # Phase 1: Parallel chart capture
    logger.info(f"Starting parallel chart capture (max {max_concurrent_tickers} concurrent)")

    async with AsyncBrowserManager(config) as browser:
        semaphore = asyncio.Semaphore(max_concurrent_tickers)

        async def process_ticker(ticker_info: dict) -> tuple[str, dict[str, Path] | Exception]:
            symbol = ticker_info["symbol"]
            name = ticker_info.get("name", symbol)

            async with semaphore:
                logger.info(f"Processing {symbol} ({name})")
                try:
                    paths = await chart_capture.capture(browser, symbol)
                    return (symbol, paths)
                except Exception as e:
                    logger.error(f"Error capturing {symbol}: {e}")
                    return (symbol, e)

        # Capture all tickers in parallel (limited by semaphore)
        capture_results = await asyncio.gather(
            *[process_ticker(t) for t in tickers],
            return_exceptions=True
        )

        for result in capture_results:
            if isinstance(result, Exception):
                errors.append(("unknown", result))
            else:
                symbol, paths_or_error = result
                if isinstance(paths_or_error, Exception):
                    errors.append((symbol, paths_or_error))
                else:
                    screenshots[symbol] = paths_or_error

    # Phase 2: Batch Claude analysis
    results: list[AnalysisResult] = []
    if not dry_run and screenshots:
        logger.info(f"Starting batch analysis for {len(screenshots)} tickers")
        results = await analyzer.analyze_batch(screenshots, max_concurrent=5)

        # Log recommendations
        for result in results:
            rec = result.recommendation
            logger.info(
                f"{result.symbol}: {rec.get('signal', 'N/A')} "
                f"(Confidence: {rec.get('confidence', 'N/A')})"
            )

    # Phase 3: Send email report (sync is fine - runs once at end)
    if send_email and not dry_run and results:
        email_sender = EmailSender(config)
        try:
            email_sender.send_report(results, screenshots)
        except Exception as e:
            logger.error(f"Failed to send email report: {e}")
            errors.append(("email", e))

    # Phase 4: Write JSON results for downstream consumption (e.g. Carlos morning brief)
    if results:
        import json
        results_path = get_project_root() / "output" / "results.json"
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_data = {
            "run_at": datetime.now().isoformat(),
            "results": [
                {
                    "symbol": r.symbol,
                    "analysis_date": r.analysis_date,
                    "primary_trend": r.primary_trend,
                    "secondary_trend": r.secondary_trend,
                    "patterns_identified": r.patterns_identified,
                    "support_levels": r.support_levels,
                    "resistance_levels": r.resistance_levels,
                    "volume_assessment": r.volume_assessment,
                    "rsi": r.rsi,
                    "recommendation": r.recommendation,
                    "key_observations": r.key_observations,
                    "summary": r.summary,
                }
                for r in results
            ],
        }
        results_path.write_text(json.dumps(results_data, indent=2))
        logger.info(f"Results written to {results_path}")

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

    # Run async analysis
    try:
        results, screenshots = asyncio.run(
            run_analysis_async(
                config=config,
                tickers=tickers,
                send_email=not args.no_email,
                dry_run=args.dry_run,
                max_concurrent_tickers=args.max_concurrent,
            )
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
