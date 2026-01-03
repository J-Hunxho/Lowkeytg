from __future__ import annotations

import argparse
import asyncio

from aiogram import Bot

from .config import get_settings
from .logging import configure_logging, logger


async def set_webhook(bot: Bot, webhook_url: str, secret_token: str) -> None:
    await bot.set_webhook(
        url=webhook_url,
        secret_token=secret_token,
    )
    logger.info("webhook.set", url=webhook_url)


async def delete_webhook(bot: Bot) -> None:
    await bot.delete_webhook()
    logger.info("webhook.deleted")


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram webhook management")
    parser.add_argument(
        "action",
        choices=["set-webhook", "delete-webhook"],
        help="Action to perform",
    )
    args = parser.parse_args()

    configure_logging()

    settings = get_settings()

    if not settings.telegram_enabled:
        raise RuntimeError("Telegram is disabled (telegram_enabled=false)")

    settings.validate_telegram()

    # Import bot lazily AFTER config is validated
    from .bot.main import bot

    if args.action == "set-webhook":
        asyncio.run(
            set_webhook(
                bot=bot,
                webhook_url=settings.webhook_url,
                secret_token=settings.telegram_webhook_secret_token.get_secret_value(),
            )
        )
    else:
        asyncio.run(delete_webhook(bot))


if __name__ == "__main__":
    main()
