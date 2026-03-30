from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest

import stripe
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..bootstrap import safe_sync_bot_state
from ..bot.main import get_private_commands
from ..config import get_settings
from ..db import check_database_health, close_engine
from ..logging import configure_logging, logger
from ..models import AccessGrant, AdminSetting, Order, StripeSubscription, User, UserBadge, UserStreak
from ..schemas import (
    AIChatRequest,
    AIChatResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    HealthResponse,
    ReadinessResponse,
)
from ..services.admin import AdminService
from ..services.ai import AIService
from ..services.ai.service import AIQuotaExceeded, AIServiceDisabled
from ..services.payments import PaymentsService
from ..services.rate_limit import RateLimiter
from .deps import get_bot, get_db_session, get_dispatcher, get_rate_limiter

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.info(
        "startup.diagnostics",
        env=settings.env,
        telegram_enabled=settings.telegram_enabled,
        stripe_enabled=settings.stripe_enabled,
        webhook_path=settings.webhook_path,
        set_webhook_on_start=settings.set_webhook_on_start,
    )

    if settings.telegram_enabled:
        try:
            settings.validate_telegram()
            logger.info("startup.telegram_config_valid")
        except RuntimeError as exc:
            logger.warning("startup.telegram_config_invalid", error=str(exc))
            if settings.fail_fast_on_startup:
                raise

    if settings.stripe_enabled:
        try:
            settings.validate_stripe()
            logger.info("startup.stripe_config_valid")
        except RuntimeError as exc:
            logger.warning("startup.stripe_config_invalid", error=str(exc))
            if settings.fail_fast_on_startup:
                raise
    try:
        settings.validate_ai()
        logger.info("startup.ai_config_valid", ai_enabled=settings.ai_enabled, ai_provider=settings.ai_provider)
    except RuntimeError as exc:
        logger.warning("startup.ai_config_invalid", error=str(exc))
        if settings.fail_fast_on_startup:
            raise

    await safe_sync_bot_state(get_bot(), settings, get_private_commands)
    yield
    await close_engine()
    logger.info("shutdown.complete")


app = FastAPI(title="Elite Telegram Bot", version="0.6.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="src/app/web/static"), name="static")
MINI_APP_TEMPLATE = Path("src/app/web/templates/miniapp.html")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("request.validation_error", errors=exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("app.unhandled_exception", error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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

    checks["ai_config"] = "disabled"
    if settings.ai_enabled:
        try:
            settings.validate_ai()
            checks["ai_config"] = "ok"
        except RuntimeError as exc:
            logger.warning("health.ai_config_invalid", error=str(exc))
            checks["ai_config"] = "invalid"
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


@app.get("/api/catalog")
async def catalog(session: AsyncSession = Depends(get_db_session)) -> JSONResponse:
    service = PaymentsService(session=session)
    products = await service.product_catalog()
    return JSONResponse({"items": products})


@app.get("/api/account/state")
async def account_state(telegram_id: int, session: AsyncSession = Depends(get_db_session)) -> JSONResponse:
    try:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    except Exception as exc:
        logger.warning("account.state_unavailable", error=str(exc))
        return JSONResponse({"orders_count": 0, "subscriptions_count": 0, "active_access_count": 0, "is_admin": False, "streak_days": 0, "badges": [], "ai": {"tier": "free", "daily_limit": 0, "used_today": 0, "remaining_today": 0}})

    if user is None:
        return JSONResponse({"orders_count": 0, "subscriptions_count": 0, "active_access_count": 0, "is_admin": False, "streak_days": 0, "badges": [], "ai": {"tier": "free", "daily_limit": 0, "used_today": 0, "remaining_today": 0}})

    orders_count = await session.scalar(select(func.count(Order.id)).where(Order.user_id == user.id))
    subscriptions_count = await session.scalar(select(func.count(StripeSubscription.id)).where(StripeSubscription.user_id == user.id, StripeSubscription.status.in_(["active", "trialing", "past_due"])))
    active_access_count = await session.scalar(select(func.count(AccessGrant.id)).where(AccessGrant.user_id == user.id, AccessGrant.active.is_(True)))
    streak = await session.scalar(select(UserStreak).where(UserStreak.user_id == user.id))
    badges = list((await session.execute(select(UserBadge).where(UserBadge.user_id == user.id).order_by(UserBadge.granted_at.desc()).limit(5))).scalars())
    try:
        ai_status = await AIService(session).usage_snapshot(user)
    except AIServiceDisabled:
        ai_status = {"tier": "disabled", "daily_limit": 0, "used_today": 0, "remaining_today": 0, "provider": "n/a", "model": "n/a"}
    return JSONResponse(
        {
            "orders_count": int(orders_count or 0),
            "subscriptions_count": int(subscriptions_count or 0),
            "active_access_count": int(active_access_count or 0),
            "is_admin": bool(user.is_admin),
            "streak_days": int(streak.current_streak if streak else 0),
            "badges": [badge.label for badge in badges],
            "ai": ai_status,
        }
    )


@app.post("/api/ai/chat", response_model=AIChatResponse)
async def ai_chat(
    payload: AIChatRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AIChatResponse:
    user = await session.scalar(select(User).where(User.telegram_id == payload.telegram_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    service = AIService(session)
    try:
        response = await service.respond(user=user, prompt=payload.prompt)
    except AIQuotaExceeded as exc:
        await session.commit()
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIServiceDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await session.commit()
    return AIChatResponse(**response)


@app.get("/payments/success", response_class=HTMLResponse)
async def payment_success() -> HTMLResponse:
    return HTMLResponse("<html><body><h2>Payment successful</h2><p>Return to Telegram to use your unlocked access.</p></body></html>")


@app.get("/payments/cancel", response_class=HTMLResponse)
async def payment_cancel() -> HTMLResponse:
    return HTMLResponse("<html><body><h2>Payment cancelled</h2><p>No charge was completed. You can retry from Telegram.</p></body></html>")


@app.get("/mini-app", response_class=HTMLResponse)
async def mini_app() -> HTMLResponse:
    return HTMLResponse(content=MINI_APP_TEMPLATE.read_text(encoding="utf-8"))


async def _telegram_webhook(
    request: Request,
    bot: Bot | None,
    dispatcher: Dispatcher,
    session: AsyncSession,
    rate_limiter: RateLimiter,
    secret_token: str | None,
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
    if not secret_token or not compare_digest(secret_token, expected):
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
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception("telegram_webhook.error", error=str(exc), update_id=payload.get("update_id"))
        raise HTTPException(status_code=500, detail="Failed to process update") from exc

    return JSONResponse({"ok": True})


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    bot: Bot | None = Depends(get_bot),
    dispatcher: Dispatcher = Depends(get_dispatcher),
    session: AsyncSession = Depends(get_db_session),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    secret_token: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> JSONResponse:
    return await _telegram_webhook(request, bot, dispatcher, session, rate_limiter, secret_token)


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
    order = await service.handle_stripe_event(event)
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


async def _require_admin(session: AsyncSession, admin_telegram_id: int) -> User:
    cfg = get_settings()
    try:
        if admin_telegram_id in cfg.admin_user_ids:
            user = await session.scalar(select(User).where(User.telegram_id == admin_telegram_id))
            if user is None:
                raise HTTPException(status_code=403, detail="Admin access required")
            user.is_admin = True
            return user

        user = await session.scalar(select(User).where(User.telegram_id == admin_telegram_id))
        if user is None:
            raise HTTPException(status_code=403, detail="Admin access required")

        if user.is_admin:
            return user

        setting = await session.scalar(select(AdminSetting).where(AdminSetting.key == "admin_user_ids"))
        ids = setting.value if setting and isinstance(setting.value, list) else []
        if admin_telegram_id in ids:
            user.is_admin = True
            return user
    except SQLAlchemyError as exc:
        logger.warning("admin.auth_lookup_failed", admin_telegram_id=admin_telegram_id, error=str(exc))
        raise HTTPException(status_code=403, detail="Admin access required") from exc

    raise HTTPException(status_code=403, detail="Admin access required")


@app.get("/api/admin/settings")
async def admin_get_settings(
    admin_telegram_id: int = Header(alias="X-Admin-Telegram-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    await _require_admin(session, admin_telegram_id)
    service = AdminService(session)
    return JSONResponse({"items": [{"key": k, "value": v} for k, v in (await service.settings_map()).items()]})


@app.put("/api/admin/settings/{key}")
async def admin_put_setting(
    key: str,
    payload: object = Body(...),
    admin_telegram_id: int = Header(alias="X-Admin-Telegram-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    admin_user = await _require_admin(session, admin_telegram_id)
    service = AdminService(session)
    await service.upsert_setting(key, payload)
    if key == "admin_user_ids" and isinstance(payload, list):
        await service.set_admin_users([int(v) for v in payload if str(v).isdigit()])
    await session.commit()
    logger.info("admin.setting_updated", key=key, admin_telegram_id=admin_user.telegram_id)
    return JSONResponse({"ok": True, "key": key})


@app.post("/admin/sync-products")
async def admin_sync_products_alias(
    admin_telegram_id: int = Header(alias="X-Admin-Telegram-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    return await admin_sync_catalog(admin_telegram_id=admin_telegram_id, session=session)


@app.post("/api/admin/catalog/sync")
async def admin_sync_catalog(
    admin_telegram_id: int = Header(alias="X-Admin-Telegram-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    admin_user = await _require_admin(session, admin_telegram_id)
    service = PaymentsService(session=session)
    admin_service = AdminService(session)
    try:
        synced = await service.sync_products_from_stripe()
        await admin_service.record_sync_run("stripe", "success", f"synced={synced}", admin_user.id)
        await session.commit()
        return JSONResponse({"ok": True, "synced": synced})
    except Exception as exc:
        logger.exception("admin.sync_catalog_failed", error=str(exc), admin_telegram_id=admin_user.telegram_id)
        await admin_service.record_sync_run("stripe", "failed", str(exc), admin_user.id)
        await session.commit()
        raise HTTPException(status_code=502, detail="Stripe sync failed") from exc




@app.get("/api/admin/dashboard")
async def admin_dashboard(
    admin_telegram_id: int = Header(alias="X-Admin-Telegram-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    await _require_admin(session, admin_telegram_id)
    service = AdminService(session)
    return JSONResponse(await service.dashboard())


@app.patch("/api/admin/products/{sku}")
async def admin_patch_product(
    sku: str,
    payload: dict,
    admin_telegram_id: int = Header(alias="X-Admin-Telegram-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    admin_user = await _require_admin(session, admin_telegram_id)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    service = AdminService(session)
    product = await service.set_product_overrides(sku, payload)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    await session.commit()
    logger.info("admin.product_updated", sku=sku, admin_telegram_id=admin_user.telegram_id)
    return JSONResponse({"ok": True, "sku": sku})


@app.post("/api/admin/access")
async def admin_access_update(
    payload: dict,
    admin_telegram_id: int = Header(alias="X-Admin-Telegram-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    admin_user = await _require_admin(session, admin_telegram_id)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    telegram_id = int(payload.get("telegram_id", 0))
    sku = str(payload.get("sku", "")).strip()
    active = bool(payload.get("active", True))
    if telegram_id <= 0 or not sku:
        raise HTTPException(status_code=400, detail="telegram_id and sku required")
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    service = AdminService(session)
    await service.manual_grant(user, sku, active)
    await session.commit()
    logger.info("admin.access_updated", target_telegram_id=telegram_id, sku=sku, active=active, admin_telegram_id=admin_user.telegram_id)
    return JSONResponse({"ok": True})

settings_for_route = get_settings()
if settings_for_route.webhook_path != "/webhook/telegram":
    app.add_api_route(
        path=settings_for_route.webhook_path,
        endpoint=telegram_webhook,
        methods=["POST"],
        include_in_schema=False,
    )
