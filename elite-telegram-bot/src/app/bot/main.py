from flask import Flask
import os
import threading

from __future__ import annotations

from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from ..config import settings
from ..services.rate_limit import RateLimiter
from .handlers import admin, base, payments
from .middlewares import BanMiddleware, RateLimitMiddleware, UserContextMiddleware

import os
from contextlib import asynccontextmanager
from http import HTTPStatus
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_DOMAIN: str = os.getenv('RAILWAY_PUBLIC_DOMAIN')

# Build the Telegram Bot application
bot_builder = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .updater(None)
    .build()
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """ Sets the webhook for the Telegram Bot and manages its lifecycle (start/stop). """
    await bot_builder.bot.setWebhook(url=WEBHOOK_DOMAIN)
    async with bot_builder:
        await bot_builder.start()
        yield
        await bot_builder.stop()


app = FastAPI(lifespan=lifespan)


@app.post("/")
async def process_update(request: Request):
    """ Handles incoming Telegram updates and processes them with the bot. """
    message = await request.json()
    update = Update.de_json(data=message, bot=bot_builder.bot)
    await bot_builder.process_update(update)
    return Response(status_code=HTTPStatus.OK)


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """ Handles the /start command by sending a "Hello world!" message in response. """
    await update.message.reply_text("Hello! 🍡 Send me a message and I'll echo it back to you")

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def create_bot() -> Bot:
    session = AiohttpSession()
    return Bot(token=settings.telegram_bot_token.get_secret_value(), session=session, parse_mode="MarkdownV2")


def _build_rate_limiter() -> RateLimiter:
    redis_client: Optional[Redis] = None
    if settings.redis_url and Redis:
        redis_client = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return RateLimiter(redis_client)


def create_dispatcher(rate_limiter: Optional[RateLimiter] = None) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(base.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)

    dp.update.outer_middleware(UserContextMiddleware())
    dp.update.outer_middleware(BanMiddleware())
    limiter = rate_limiter or _build_rate_limiter()
    dp.update.outer_middleware(RateLimitMiddleware(limiter))

    return dp


bot = create_bot()
rate_limiter = _build_rate_limiter()
dispatcher = create_dispatcher(rate_limiter)

threading.Thread(target=start_health_server, daemon=True).start()

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}
