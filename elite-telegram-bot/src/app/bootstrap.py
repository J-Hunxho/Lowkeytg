from __future__ import annotations

import asyncio

from aiogram import Bot

from .bot.main import bot
from .config import settings
from .logging import configure_logging, logger


async def _set_webhook(bot: Bot) -> None:
    await bot.set_webhook(url=settings.webhook_url, secret_token=settings.telegram_webhook_secret_token.get_secret_value())
    logger.info("webhook.set", url=settings.webhook_url)


async def _delete_webhook(bot: Bot) -> None:
    await bot.delete_webhook()
    logger.info("webhook.deleted")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Telegram webhook management")
    parser.add_argument("action", choices=["set-webhook", "delete-webhook"], help="Action to perform")
    args = parser.parse_args()
    configure_logging()

    if args.action == "set-webhook":
        asyncio.run(_set_webhook(bot))
    else:
        asyncio.run(_delete_webhook(bot))


if __name__ == "__main__":
    main()
