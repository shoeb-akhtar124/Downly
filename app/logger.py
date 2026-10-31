"""
Local Rotating Logger for Downly.
Provides safe, rotating file logging with automatic redaction of sensitive credentials.
Never logs authentication cookies, passwords, or tokens.
"""
import os
import re
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from app.constants import APP_LOG_FILE, USER_LOGS_DIR

_logger: Optional[logging.Logger] = None

# Sensitive regex patterns to redact
_SENSITIVE_PATTERNS = [
    re.compile(r'(password[:=]\s*)([^\s&]+)', re.IGNORECASE),
    re.compile(r'(token[:=]\s*)([^\s&]+)', re.IGNORECASE),
    re.compile(r'(auth[:=]\s*)([^\s&]+)', re.IGNORECASE),
    re.compile(r'(cookie[:=]\s*)([^\s&]+)', re.IGNORECASE),
    re.compile(r'(secret[:=]\s*)([^\s&]+)', re.IGNORECASE),
]


class RedactingFormatter(logging.Formatter):
    """Custom formatter that strips sensitive query parameters and credentials."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pattern in _SENSITIVE_PATTERNS:
            msg = pattern.sub(r'\1[REDACTED]', msg)
        return msg


def get_logger() -> logging.Logger:
    """Initialize and return the singleton application logger."""
    global _logger
    if _logger is not None:
        return _logger

    USER_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    _logger = logging.getLogger("Downly")
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

    # Prevent duplicate handlers
    if not _logger.handlers:
        # Rotating File Handler: max 5 MB per file, up to 3 backups
        file_handler = RotatingFileHandler(
            str(APP_LOG_FILE),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        formatter = RedactingFormatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)

        # Console Handler (standard output for development)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        _logger.addHandler(console_handler)

    return _logger


def log_info(msg: str) -> None:
    get_logger().info(msg)


def log_warning(msg: str) -> None:
    get_logger().warning(msg)


def log_error(msg: str, exc_info: bool = False) -> None:
    get_logger().error(msg, exc_info=exc_info)

