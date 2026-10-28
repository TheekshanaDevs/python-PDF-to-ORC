"""Logging configuration for the application."""

import logging
import sys
from pathlib import Path


def setup_logging(log_file: Path | None = None, debug: bool = False) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        log_file: Path to the processing.log file. If None, log only to stderr.
        debug: If True, set log level to DEBUG; otherwise INFO.

    Returns:
        The configured root application logger.
    """
    logger = logging.getLogger("pdfnotes")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Remove any existing handlers to avoid duplicates on re-init
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — only warnings and above so we don't interfere with Rich
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING if not debug else logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler — captures everything at DEBUG level
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
