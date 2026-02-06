"""Utility functions for logging, config loading, and retry logic."""

import asyncio
import logging
import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import yaml
from dotenv import load_dotenv


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def load_config() -> dict:
    """Load the main configuration file."""
    config_path = get_project_root() / "config" / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_tickers() -> list[dict]:
    """Load the ticker list from configuration."""
    tickers_path = get_project_root() / "config" / "tickers.yaml"
    with open(tickers_path, "r") as f:
        data = yaml.safe_load(f)
        return data.get("tickers", [])


def load_env() -> None:
    """Load environment variables from .env file."""
    env_path = get_project_root() / "config" / ".env"
    load_dotenv(env_path)


def setup_logging(config: dict) -> logging.Logger:
    """Set up logging with configuration."""
    log_config = config.get("logging", {})
    log_level = getattr(logging, log_config.get("level", "INFO"))
    log_format = log_config.get(
        "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create logs directory if it doesn't exist
    log_dir = get_project_root() / "logs"
    log_dir.mkdir(exist_ok=True)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "stockcharts.log"),
        ],
    )

    return logging.getLogger("stockcharts")


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger = logging.getLogger("stockcharts")
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Async retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger = logging.getLogger("stockcharts")
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception

        return wrapper

    return decorator


def get_screenshot_path(symbol: str) -> Path:
    """Get the path for saving a chart screenshot."""
    screenshots_dir = get_project_root() / "output" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir / f"{symbol}.png"


def ensure_env_vars(*var_names: str) -> dict[str, str]:
    """
    Ensure required environment variables are set.

    Args:
        *var_names: Names of required environment variables

    Returns:
        Dictionary of environment variable names to values

    Raises:
        EnvironmentError: If any required variable is not set
    """
    missing = []
    values = {}

    for var_name in var_names:
        value = os.getenv(var_name)
        if not value:
            missing.append(var_name)
        else:
            values[var_name] = value

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Please set them in config/.env"
        )

    return values
