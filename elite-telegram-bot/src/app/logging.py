import logging
import sys

from .config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    log_level = settings.log_level.upper() if settings.log_level else "INFO"

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


logger = logging.getLogger("elite-bot")
