"""Logging configuration for TITrack."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from titrack.config.paths import get_data_dir, is_frozen

# Module-level logger
_logger: Optional[logging.Logger] = None

# Constants
LOG_FILENAME = "titrack.log"
MAX_BYTES = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_log_path(portable: bool = False) -> Path:
    """Get the path to the log file."""
    data_dir = get_data_dir(portable=portable)
    return data_dir / LOG_FILENAME


def setup_logging(portable: bool = False, console: bool = True) -> logging.Logger:
    """
    Configure and return the application logger.

    Args:
        portable: If True, use portable data directory for log file
        console: If True, also log to console (useful for debugging)

    Returns:
        Configured logger instance
    """
    global _logger

    if _logger is not None:
        return _logger

    logger = logging.getLogger("titrack")
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # File handler with rotation
    log_path = get_log_path(portable=portable)
    try:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If we can't create log file, continue without file logging
        print(f"Warning: Could not create log file at {log_path}: {e}")

    # Console handler (optional - for debugging or when console is visible)
    if console and not is_frozen():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """
    Get the application logger.

    If logging hasn't been set up yet, sets up with defaults.
    """
    global _logger
    if _logger is None:
        return setup_logging()
    return _logger
