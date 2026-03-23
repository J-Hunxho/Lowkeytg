from __future__ import annotations

import json

import stripe
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..bootstrap import safe_sync_bot_state
from ..bot.main import get_private_commands
from ..config import get_settings
from ..db import check_database_health, close_engine
from ..logging import configure_logging, logger
from ..schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    HealthResponse,
    ReadinessResponse,
)
from ..services.payments import PaymentsService
from ..services.rate_limit import RateLimiter
from .deps import get_bot, get_db_session, get_dispatcher, get_rate_limiter


configure_logging()

app = FastAPI(title="Elite Telegram Bot", version="0.4.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("request.validation_error", errors=exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("app.unhandled_exception", error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.on_event("startup")
async def on_startup() -> None:
    settings = get_settings()
    await safe_sync_bot_state(get_bot(), settings, get_private_commands)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_engine()
    logger.info("shutdown.complete")


@app.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    return HealthResponse()


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse()


@app.get("/readyz", response_model=ReadinessResponse)
async def readyz() -> ReadinessResponse:
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        await check_database_health()
        checks["database"] = "ok"
    except Exception as exc:
        logger.exception("health.database_failed", error=str(exc))
        checks["database"] = "failed"
        return ReadinessResponse(status="degraded", checks=checks)

    checks["telegram_config"] = "ok"
    if settings.telegram_enabled:
        try:
            settings.validate_telegram()
        except RuntimeError as exc:
            logger.warning("health.telegram_config_invalid", error=str(exc))
            checks["telegram_config"] = "invalid"
            return ReadinessResponse(status="degraded", checks=checks)

    checks["stripe_config"] = "disabled"
    if settings.stripe_enabled:
        try:
            settings.validate_stripe()
            checks["stripe_config"] = "ok"
        except RuntimeError as exc:
            logger.warning("health.stripe_config_invalid", error=str(exc))
            checks["stripe_config"] = "invalid"
            return ReadinessResponse(status="degraded", checks=checks)

    return ReadinessResponse(status="ok", checks=checks)


@app.get("/health/webhook")
async def webhook_health(bot: Bot | None = Depends(get_bot)) -> JSONResponse:
    settings = get_settings()
    if not settings.telegram_enabled or bot is None:
        return JSONResponse({"enabled": False, "configured": False, "url": None})

    info = await bot.get_webhook_info()
    return JSONResponse(
        {
            "enabled": True,
            "configured": info.url == settings.webhook_url,
            "expected_url": settings.webhook_url,
            "actual_url": info.url,
            "pending_updates": info.pending_update_count,
            "last_error_message": info.last_error_message,
        }
    )


@app.get("/mini-app", response_class=HTMLResponse)
async def mini_app() -> HTMLResponse:
    html = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Lowkey Mini App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
      body { font-family: Inter, system-ui, sans-serif; background: #0f1115; color: #f5f5f5; margin: 0; padding: 1.5rem; }
      .card { max-width: 560px; margin: 0 auto; padding: 1.25rem; border-radius: 16px; background: #191c22; border: 1px solid #2f3541; }
      h1 { margin-top: 0; font-size: 1.15rem; }
      button { width: 100%; border: 0; padding: .85rem 1rem; border-radius: 12px; font-weight: 600; background: linear-gradient(180deg,#d3af66,#b68a3f); color:#111; }
      code { color: #d3af66; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Lowkey Mini App</h1>
      <p>Connected to your Telegram bot session.</p>
      <p id="user"></p>
      <button id="send">Send context to bot</button>
      <p><small>Railway-ready endpoint: <code>/mini-app</code>.</small></p>
    </div>
    <script>
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();
      const user = tg.initDataUnsafe?.user;
      document.getElementById('user').textContent =
        user ? `Signed in as @${user.username || user.first_name}` :
        'Opened outside Telegram (preview mode).';

      document.getElementById('send').addEventListener('click', () => {
        tg.sendData(JSON.stringify({ action: 'mini_app_opened', at: new Date().toISOString() }));
        tg.HapticFeedback?.notificationOccurred('success');
      });
    </script>
  </body>
</html>
"""
    return HTMLResponse(content=html)


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    bot: Bot | None = Depends(get_bot),
    dispatcher: Dispatcher = Depends(get_dispatcher),
    session: AsyncSession = Depends(get_db_session),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    secret_token: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> JSONResponse:
    settings = get_settings()

    if not settings.telegram_enabled:
        raise HTTPException(status_code=403, detail="Telegram disabled")

    if bot is None:
        raise HTTPException(status_code=503, detail="Bot unavailable")

    settings.validate_telegram()

    expected_secret = settings.telegram_webhook_secret_token
    if expected_secret is None:
        raise HTTPException(status_code=503, detail="Webhook secret unavailable")

    expected = expected_secret.get_secret_value()
    if secret_token != expected:
        logger.warning("telegram_webhook.invalid_secret")
        raise HTTPException(status_code=401, detail="Invalid secret token")

    if not await rate_limiter.allow_global("telegram", limit=300, window_seconds=1):
        raise HTTPException(status_code=429, detail="Too many updates")

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
        update = Update.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("telegram_webhook.invalid_payload", error=str(exc))
        raise HTTPException(status_code=400, detail="Invalid Telegram update payload") from exc

    try:
        await dispatcher.feed_webhook_update(
            bot=bot,
            update=update,
            data={"session": session, "rate_limiter": rate_limiter},
        )
    except Exception as exc:
        logger.exception("telegram_webhook.error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to process update") from exc

    return JSONResponse({"ok": True})


@app.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    bot: Bot | None = Depends(get_bot),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    settings = get_settings()

    if not settings.stripe_enabled:
        raise HTTPException(status_code=403, detail="Stripe disabled")

    settings.validate_stripe()

    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.stripe_webhook_secret.get_secret_value(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=401, detail="Invalid signature") from exc

    service = PaymentsService(session=session, bot=bot)
    order = await service.handle_checkout_event(event)
    return JSONResponse({"ok": True, "order_id": order.id if order else None})


@app.post("/api/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CheckoutSessionResponse:
    settings = get_settings()
    if not settings.stripe_enabled:
        raise HTTPException(status_code=403, detail="Stripe disabled")

    service = PaymentsService(session=session)
    user = await service.orders.get_user_by_telegram_id(payload.telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        checkout = await service.create_checkout_session(
            user=user,
            sku=payload.sku,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CheckoutSessionResponse(**checkout)
