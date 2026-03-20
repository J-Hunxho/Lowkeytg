from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, WebhookInfo
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import Settings, get_settings
from .logging import configure_logging, logger


CommandFactory = Callable[[], list[BotCommand]]


async def _with_retry(operation: str, task: Callable[[], Awaitable[Any]]) -> Any:
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(TelegramAPIError),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    ):
        with attempt:
            logger.info("telegram.operation_attempt", operation=operation, attempt=attempt.retry_state.attempt_number)
            return await task()


async def sync_bot_state(
    bot: Bot,
    settings: Settings,
    command_factory: CommandFactory,
) -> WebhookInfo | None:
    commands = command_factory()
    await _with_retry(
        "set_my_commands",
        lambda: bot.set_my_commands(commands=commands, scope=BotCommandScopeAllPrivateChats()),
    )
    logger.info("telegram.commands_synced", command_count=len(commands))

    if not settings.set_webhook_on_start:
        logger.info("telegram.webhook_sync_skipped", reason="SET_WEBHOOK_ON_START disabled")
        return None

    webhook_url = settings.webhook_url
    secret_token = settings.telegram_webhook_secret_token.get_secret_value()
    current = await _with_retry("get_webhook_info", bot.get_webhook_info)

    if current.url == webhook_url and current.pending_update_count >= 0:
        logger.info("telegram.webhook_already_set", url=webhook_url, pending_updates=current.pending_update_count)
        return current

    await _with_retry(
        "set_webhook",
        lambda: bot.set_webhook(
            url=webhook_url,
            secret_token=secret_token,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=False,
        ),
    )
    updated = await _with_retry("get_webhook_info", bot.get_webhook_info)
    logger.info(
        "telegram.webhook_synced",
        url=updated.url,
        pending_updates=updated.pending_update_count,
        last_error=updated.last_error_message,
    )
    return updated


async def safe_sync_bot_state(
    bot: Bot | None,
    settings: Settings,
    command_factory: CommandFactory,
) -> bool:
    if not settings.telegram_enabled:
        logger.info("startup.telegram_disabled")
        return False

    try:
        settings.validate_telegram()
    except RuntimeError as exc:
        logger.warning("startup.telegram_config_invalid", error=str(exc))
        if settings.fail_fast_on_startup:
            raise
        return False

    if bot is None:
        error = "Telegram enabled but TELEGRAM_BOT_TOKEN is missing"
        logger.warning("startup.telegram_bot_missing", error=error)
        if settings.fail_fast_on_startup:
            raise RuntimeError(error)
        return False

    try:
        await sync_bot_state(bot, settings, command_factory)
        return True
    except Exception as exc:
        logger.exception("startup.telegram_sync_failed", error=str(exc))
        if settings.fail_fast_on_startup:
            raise
        return False


async def set_webhook(bot: Bot, webhook_url: str, secret_token: str) -> None:
    await _with_retry(
        "set_webhook",
        lambda: bot.set_webhook(url=webhook_url, secret_token=secret_token),
    )
    logger.info("webhook.set", url=webhook_url)


async def delete_webhook(bot: Bot) -> None:
    await _with_retry("delete_webhook", bot.delete_webhook)
    logger.info("webhook.deleted")


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram webhook management")
    parser.add_argument(
        "action",
        choices=["set-webhook", "delete-webhook", "sync"],
        help="Action to perform",
    )
    args = parser.parse_args()

    configure_logging()

    settings = get_settings()

    if not settings.telegram_enabled:
        raise RuntimeError("Telegram is disabled (telegram_enabled=false)")

    settings.validate_telegram()

    from .bot.main import bot, get_private_commands

    if bot is None:
        raise RuntimeError("Telegram enabled but TELEGRAM_BOT_TOKEN is missing")

    if args.action == "set-webhook":
        asyncio.run(
            set_webhook(
                bot=bot,
                webhook_url=settings.webhook_url,
                secret_token=settings.telegram_webhook_secret_token.get_secret_value(),
            )
        )
    elif args.action == "delete-webhook":
        asyncio.run(delete_webhook(bot))
    else:
        asyncio.run(sync_bot_state(bot, settings, get_private_commands))


if __name__ == "__main__":
    main()
