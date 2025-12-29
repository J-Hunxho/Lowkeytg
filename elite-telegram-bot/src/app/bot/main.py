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

try:
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore

app = Flask(__name__)

@app.route("/healthz")
def healthz():
    return "ok", 200


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

threading.Thread(target=start_health_server, daemon=True).start()

bot = create_bot()
rate_limiter = _build_rate_limiter()
dispatcher = create_dispatcher(rate_limiter)

