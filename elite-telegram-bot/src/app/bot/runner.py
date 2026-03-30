from __future__ import annotations

import asyncio

from ..config import settings
from ..db import AsyncSessionLocal
from .main import bot, configure_bot_commands, dispatcher


async def start_bot() -> None:
    if bot is None:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    if settings.set_webhook_on_start:
        raise RuntimeError("Polling mode disabled while webhook mode is active (SET_WEBHOOK_ON_START=true)")

    await configure_bot_commands()

    async def session_middleware(handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result

    dispatcher.update.middleware(session_middleware)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_bot())
