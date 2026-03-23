from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from ..config import settings
from ..config import settings
from ..logging import logger
from ..services.rate_limit import RateLimiter
from ..services.rate_limit import RateLimiter
from .handlers.admin import router as admin_router
from .handlers.base import router as base_router
from .handlers.payments import router as payments_router
from .middlewares import BanMiddleware, RateLimitMiddleware, UserContextMiddleware

<<<<<<< codex/prepare-telegram-bot-for-saas-deployment-mr4yyh

def _build_bot() -> Bot | None:
    if not settings.telegram_enabled:
        return None

    if not settings.telegram_bot_token:
        logger.warning("bot.init.missing_token")
        return None

    try:
        return Bot(token=settings.telegram_bot_token.get_secret_value())
    except Exception as exc:  # pragma: no cover - invalid env token format
        logger.error("bot.init.invalid_token", error=str(exc))
        return None
=======

def _build_bot() -> Bot | None:
    if not settings.telegram_bot_token:
        return None
    return Bot(token=settings.telegram_bot_token.get_secret_value())
>>>>>>> Main


bot = _build_bot()
dispatcher = Dispatcher()
rate_limiter = RateLimiter()


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

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Launch bot"),
            BotCommand(command="help", description="List all commands"),
            BotCommand(command="profile", description="Your profile & referrals"),
            BotCommand(command="shop", description="Browse products"),
            BotCommand(command="app", description="Open Lowkey mini app"),
            BotCommand(command="orders", description="Your order history"),
            BotCommand(command="ping", description="Health check"),
        ]
    )


configure_dispatcher()
