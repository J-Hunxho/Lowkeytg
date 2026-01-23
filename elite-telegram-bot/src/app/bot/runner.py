import asyncio
from aiogram import Bot, Dispatcher

from app.config import settings
from app.bot.handlers import router  # wherever your handlers live

async def start_bot():
    token = settings.BOT_TOKEN  # your property alias we added
    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    # optional: register commands
    await bot.set_my_commands([
        BotCommand(command="start", description="Start"),
        BotCommand(command="help", description="Help"),
    ])

    await dp.start_polling(bot)
    import asyncio

if __name__ == "__main__":
    asyncio.run(start_bot())


    

