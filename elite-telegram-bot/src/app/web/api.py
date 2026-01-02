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
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse()


# ---------- TELEGRAM WEBHOOK ----------
@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    bot: Bot = Depends(get_bot),
    dispatcher: Dispatcher = Depends(get_dispatcher),
    session: AsyncSession = Depends(get_db_session),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    secret_token: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
) -> JSONResponse:
    settings = get_settings()
    settings.require_telegram()

    expected = settings.telegram_webhook_secret_token.get_secret_value()
    if secret_token != expected:
        logger.warning("telegram_webhook.invalid_secret", provided=secret_token)
        raise HTTPException(status_code=401, detail="Invalid secret token")

    if not await rate_limiter.allow_global("telegram", limit=300, window_seconds=1):
        raise HTTPException(status_code=429, detail="Too many updates")

    body = await request.body()
    data = json.loads(body)

    update = Update.model_validate(data)

    try:
        await dispatcher.feed_webhook_update(
            bot=bot,
            update=update,
            data={
                "session": session,
                "rate_limiter": rate_limiter,
            },
        )
    except Exception as exc:
        logger.exception("telegram_webhook.error", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail="Failed to process update",
        ) from exc

    return JSONResponse({"ok": True})


# ---------- STRIPE WEBHOOK ----------
@app.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    bot: Bot = Depends(get_bot),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    settings = get_settings()

    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=400, detail="Stripe webhook secret missing")

    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.stripe_webhook_secret.get_secret_value(),
        )
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("stripe_webhook.invalid_signature", error=str(exc))
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    service = PaymentsService(session=session, bot=bot)
    await service.handle_checkout_event(event.to_dict())

    return JSONResponse({"received": True})


# ---------- CHECKOUT ----------
@app.post("/payments/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CheckoutSessionResponse:
    settings = get_settings()

    if not settings.stripe_secret_key:
        raise HTTPException(status_code=400, detail="Stripe not configured")

    from ..repos.users import UserRepository

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(payload.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    service = PaymentsService(session=session, bot=None)
    checkout = await service.create_checkout_session(
        user=user,
        sku=payload.sku,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
    )

    return CheckoutSessionResponse(
        url=checkout["url"],
        session_id=checkout["session_id"],
    )
