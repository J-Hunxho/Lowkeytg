from __future__ import annotations

import logging
import sys

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


class EventLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _emit(self, level: int, event: str, **context: object) -> None:
        if context:
            payload = " ".join(f"{key}={value!r}" for key, value in sorted(context.items()))
            self._logger.log(level, "%s | %s", event, payload)
            return
        self._logger.log(level, event)

    def info(self, event: str, **context: object) -> None:
        self._emit(logging.INFO, event, **context)

    def warning(self, event: str, **context: object) -> None:
        self._emit(logging.WARNING, event, **context)

    def error(self, event: str, **context: object) -> None:
        self._emit(logging.ERROR, event, **context)

    def exception(self, event: str, **context: object) -> None:
        if context:
            payload = " ".join(f"{key}={value!r}" for key, value in sorted(context.items()))
            self._logger.exception("%s | %s", event, payload)
            return
        self._logger.exception(event)


def get_logger(name: str | None = None) -> EventLogger:
    return EventLogger(name or _LOGGER_NAME)


# Default app logger
logger = get_logger()