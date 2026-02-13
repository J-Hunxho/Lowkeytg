from __future__ import annotations

import asyncio

from .main import bot, configure_bot_commands, dispatcher


async def start_bot() -> None:
    if bot is None:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    await configure_bot_commands()
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_bot())
