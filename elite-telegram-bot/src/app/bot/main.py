from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from ..config import settings
from ..logging import logger
from ..services.rate_limit import RateLimiter
from .handlers.admin import router as admin_router
from .handlers.base import router as base_router
from .handlers.payments import router as payments_router
from .middlewares import (
    BanMiddleware,
    DBSessionMiddleware,
    RateLimitMiddleware,
    UserContextMiddleware,
)


def _build_bot() -> Bot | None:
    if not settings.telegram_enabled:
        return None
    if not settings.telegram_bot_token:
        logger.warning("bot.init.missing_token")
        return None
    try:
        return Bot(token=settings.telegram_bot_token.get_secret_value())
    except Exception as exc:  # pragma: no cover
        logger.error("bot.init.invalid_token", error=str(exc))
        return None


bot = _build_bot()
dispatcher = Dispatcher()
rate_limiter = RateLimiter()


def get_private_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Private entry"),
        BotCommand(command="shop", description="Access Drops"),
        BotCommand(command="plans", description="Membership tiers"),
        BotCommand(command="account", description="Member status"),
        BotCommand(command="orders", description="Order history"),
        BotCommand(command="badges", description="Member badges"),
        BotCommand(command="leaderboard", description="Referral leaderboard"),
        BotCommand(command="support", description="Member support"),
        BotCommand(command="ai", description="AI concierge"),
        BotCommand(command="app", description="Open mini app"),
        BotCommand(command="buy", description="Checkout by SKU"),
    ]


def get_admin_commands() -> list[BotCommand]:
    return [
        BotCommand(command="admin", description="Admin panel"),
        BotCommand(command="sync_products", description="Sync Stripe catalog"),
        BotCommand(command="reload_settings", description="Runtime checks"),
        BotCommand(command="broadcast_product", description="Promote product"),
        BotCommand(command="broadcast", description="Broadcast message"),
        BotCommand(command="stats", description="System stats"),
        BotCommand(command="users", description="User count"),
        BotCommand(command="status", description="System status"),
        BotCommand(command="webhookstatus", description="Webhook health"),
    ]


def configure_dispatcher() -> None:
    dispatcher.update.middleware(DBSessionMiddleware())
    dispatcher.update.middleware(UserContextMiddleware())
    dispatcher.update.middleware(BanMiddleware())
    dispatcher.update.middleware(RateLimitMiddleware(rate_limiter))

    dispatcher.include_router(base_router)
    dispatcher.include_router(payments_router)
    dispatcher.include_router(admin_router)


async def configure_bot_commands() -> None:
    if bot is None:
        return
    await bot.set_my_commands(commands=get_private_commands(), scope=BotCommandScopeAllPrivateChats())
    for admin_id in settings.admin_user_ids:
        await bot.set_my_commands(commands=get_admin_commands(), scope=BotCommandScopeChat(chat_id=admin_id))


configure_dispatcher()