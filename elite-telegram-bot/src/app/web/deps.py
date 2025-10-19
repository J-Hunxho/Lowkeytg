from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ..bot.main import bot, dispatcher, rate_limiter
from ..db import get_session
from ..services.rate_limit import RateLimiter


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def get_bot():
    return bot


def get_dispatcher():
    return dispatcher


def get_rate_limiter() -> RateLimiter:
    return rate_limiter
