from __future__ import annotations

import stripe

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot, Dispatcher
from aiogram.types import Update

from ..bot.main import configure_bot_commands
from ..config import get_settings
from ..db import close_engine
from ..logging import configure_logging, logger
from ..schemas import CheckoutSessionRequest, CheckoutSessionResponse, HealthResponse
from ..services.payments import PaymentsService
from ..services.rate_limit import RateLimiter
from .deps import get_bot, get_db_session, get_dispatcher, get_rate_limiter


configure_logging()

app = FastAPI(title="Elite Telegram Bot", version="0.2.0")


@app.on_event("startup")
async def on_startup() -> None:
    settings = get_settings()

    if not settings.telegram_enabled:
        logger.info("startup.telegram_disabled")
        return

    settings.validate_telegram()

    bot = get_bot()
    if bot is None:
        raise RuntimeError("Telegram enabled but TELEGRAM_BOT_TOKEN is missing")

    await configure_bot_commands()

    if settings.set_webhook_on_start:
        try:
            await bot.set_webhook(
                url=settings.webhook_url,
                secret_token=settings.telegram_webhook_secret_token.get_secret_value(),
            )
            logger.info("startup.webhook_set url=%s", settings.webhook_url)
        except Exception as exc:
            logger.warning("startup.webhook_failed", error=str(exc))


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


@app.post("webhook/telegram")
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

    expected = settings.telegram_webhook_secret_token.get_secret_value()

    if secret_token != expected:
        logger.warning("telegram_webhook.invalid_secret")
        raise HTTPException(status_code=401, detail="Invalid secret token")

    if not await rate_limiter.allow_global("telegram", limit=300, window_seconds=1):
        raise HTTPException(status_code=429, detail="Too many updates")

    update = Update.model_validate(await request.json())

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


@app.post("/payments/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CheckoutSessionResponse:

    settings = get_settings()

    if not settings.stripe_enabled:
        raise HTTPException(status_code=403, detail="Stripe disabled")

    settings.validate_stripe()

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
