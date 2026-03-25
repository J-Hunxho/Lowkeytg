from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from ..config import settings
from ..logging import logger
from ..services.rate_limit import RateLimiter
from .handlers.admin import router as admin_router
from .handlers.base import router as base_router
from .handlers.payments import router as payments_router
from .middlewares import BanMiddleware, RateLimitMiddleware, UserContextMiddleware


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
        BotCommand(command="start", description="Onboarding"),
        BotCommand(command="shop", description="Browse catalog"),
        BotCommand(command="plans", description="Compare plans"),
        BotCommand(command="account", description="Account overview"),
        BotCommand(command="support", description="Contact support"),
        BotCommand(command="ai", description="AI concierge"),
        BotCommand(command="buy", description="Buy by SKU"),
        BotCommand(command="orders", description="Order history"),
        BotCommand(command="app", description="Open mini app"),
        BotCommand(command="sync_products", description="Admin: sync Stripe catalog"),
        BotCommand(command="reload_settings", description="Admin: runtime checks"),
        BotCommand(command="broadcast_product", description="Admin: promote product"),
        BotCommand(command="broadcast", description="Admin: broadcast text"),
        BotCommand(command="status", description="System status"),
        BotCommand(command="webhookstatus", description="Webhook status"),
    ]


def configure_dispatcher() -> None:
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


configure_dispatcher()
