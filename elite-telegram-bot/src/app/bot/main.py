from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from ..config import settings
from ..services.rate_limit import RateLimiter
from .handlers.admin import router as admin_router
from .handlers.base import router as base_router
from .handlers.payments import router as payments_router
from .middlewares import BanMiddleware, RateLimitMiddleware, UserContextMiddleware


def _build_bot() -> Bot | None:
    if not settings.telegram_bot_token:
        return None
    return Bot(token=settings.telegram_bot_token.get_secret_value())


bot = _build_bot()
dispatcher = Dispatcher()
rate_limiter = RateLimiter()


def get_private_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="User · onboarding flow"),
        BotCommand(command="help", description="User · command guide"),
        BotCommand(command="account", description="User · account overview"),
        BotCommand(command="profile", description="User · account alias"),
        BotCommand(command="orders", description="User · order history"),
        BotCommand(command="support", description="User · support contact"),
        BotCommand(command="app", description="Products · launch mini app"),
        BotCommand(command="shop", description="Products · browse catalog"),
        BotCommand(command="products", description="Products · list live SKUs"),
        BotCommand(command="buy", description="Products · purchase by SKU"),
        BotCommand(command="admin", description="Admin · control panel"),
        BotCommand(command="addproduct", description="Admin · add product"),
        BotCommand(command="removeproduct", description="Admin · remove product"),
        BotCommand(command="broadcast", description="Admin · send broadcast"),
        BotCommand(command="stats", description="Admin · performance metrics"),
        BotCommand(command="users", description="Admin · user totals"),
        BotCommand(command="ban", description="Admin · block a user"),
        BotCommand(command="unban", description="Admin · restore a user"),
        BotCommand(command="webhookstatus", description="System · webhook status"),
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

    await bot.set_my_commands(
        commands=get_private_commands(),
        scope=BotCommandScopeAllPrivateChats(),
    )


configure_dispatcher()
