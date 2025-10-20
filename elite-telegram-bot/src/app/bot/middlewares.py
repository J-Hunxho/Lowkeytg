from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..repos.bans import BanRepository
from ..repos.users import UserRepository
from ..services.rate_limit import RateLimiter

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class UserContextMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        session: AsyncSession | None = data.get("session")
        telegram_user = getattr(event, "from_user", None)
        if not session or telegram_user is None:
            return await handler(event, data)
        repo = UserRepository(session)
        user = await repo.create_or_update(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
            is_admin=telegram_user.id in settings.admin_user_ids,
        )
        data["user"] = user
        return await handler(event, data)


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        session: AsyncSession | None = data.get("session")
        user = data.get("user")
        bot = data.get("bot")
        if not session or user is None:
            return await handler(event, data)
        repo = BanRepository(session)
        ban = await repo.get_by_user_id(user.id)
        if ban:
            if bot and isinstance(event, Message):
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text="You are banned from using this bot.",
                )
            return None
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limiter: RateLimiter) -> None:
        self.limiter = limiter

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("user")
        bot = data.get("bot")
        data.setdefault("rate_limiter", self.limiter)
        if user is None:
            return await handler(event, data)
        allowed = await self.limiter.allow_user(user.telegram_id, "messages", limit=20, window_seconds=30)
        if not allowed:
            if bot and isinstance(event, Message):
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text="Slow down — you are sending messages too quickly.",
                )
            return None
        return await handler(event, data)
