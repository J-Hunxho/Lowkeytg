from __future__ import annotations

import json
import stripe

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot, Dispatcher
from aiogram.types import Update

from ..config import get_settings
from ..logging import configure_logging, logger
from ..schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    HealthResponse,
)
from ..services.payments import PaymentsService
from ..services.rate_limit import RateLimiter
from .deps import get_bot, get_db_session, get_dispatcher, get_rate_limiter
from ..bot.main import bot as bot_instance

configure_logging()

app = FastAPI(title="Elite Telegram Bot", version="0.1.0")


# ---------- STARTUP ----------
@app.on_event("startup")
async def on_startup() -> None:
    settings = get_settings()

    if not settings.set_webhook_on_start:
        return

    try:
        settings.require_telegram()

        await bot_instance.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.telegram_webhook_secret_token.get_secret_value(),
        )
        logger.info("startup.webhook_set", url=settings.webhook_url)

    except Exception as exc:
        logger.warning("startup.webhook_skipped", error=str(exc))


# ---------- HEALTH ----------
@app.get("/", response_model=HealthResponse)
async def hea

