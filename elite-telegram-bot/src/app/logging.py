from __future__ import annotations

import logging
import sys
from typing import Optional

from .config import get_settings


_LOGGER_NAME = "elite-bot"


def configure_logging(force: bool = False) -> None:
    """
    Idempotent logging configuration.
    Safe to call multiple times.
    """
    settings = get_settings()
    level_name = (settings.log_level or "INFO").upper()

    root = logging.getLogger()

    # Prevent duplicate handlers unless forced
    if root.handlers and not force:
        return

    root.setLevel(level_name)

    # Clear existing handlers if forcing reconfig
    if force:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level_name)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a namespaced logger.
    """
    return logging.getLogger(name or _LOGGER_NAME)


# Default app logger
logger = get_logger()
