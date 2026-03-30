from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import settings
from ..models import TelegramProfile
from ..repos.users import UserRepository
from ..repos.bans import BanRepository
from ..services.rate_limit import RateLimiter
from ..services.retention import RetentionService

Handler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]

logger = logging.getLogger(__name__)


# =========================
# USER CONTEXT + TRACKING
# =========================
class UserContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession | None = data.get("session")
        telegram_user = getattr(event, "from_user", None)

        if not session:
            raise RuntimeError("Session middleware not initialized")
            
        if not telegram_user:
            return await handler(event, data)

        try:
            repo = UserRepository(session)

            user = await repo.create_or_update(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                language_code=telegram_user.language_code,
                is_admin=telegram_user.id in settings.admin_user_ids,
            )

            profile = await session.scalar(
                select(TelegramProfile).where(TelegramProfile.user_id == user.id)
            )

            if not profile:
                profile = TelegramProfile(
                    user_id=user.id,
                    telegram_id=telegram_user.id,
                )
                session.add(profile)
                await session.flush()

            # 🔥 Behavioral tracking
            profile.telegram_id = telegram_user.id
            profile.username = telegram_user.username
            profile.first_name = telegram_user.first_name
            profile.last_name = telegram_user.last_name
            profile.language_code = telegram_user.language_code
            profile.last_seen_at = datetime.utcnow()

            # optional counter (add column if you want)
            if hasattr(profile, "message_count"):
                profile.message_count = (profile.message_count or 0) + 1

            data["user"] = user
            data["profile"] = profile
            data["session"] = session

            try:
                await RetentionService(session).touch_login(user)
            except Exception:
                logger.exception("UserContextMiddleware retention update failed", telegram_id=telegram_user.id)

            await session.commit()

        except Exception:
            logger.exception("UserContextMiddleware failure")
            await session.rollback()
            return None

        return await handler(event, data)


# =========================
# BAN ENFORCEMENT
# =========================
class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession | None = data.get("session")
        user = data.get("user")
        bot = data.get("bot")

        if not session or not user:
            return await handler(event, data)

        try:
            repo = BanRepository(session)
            ban = await repo.get_by_user_id(user.id)

            if ban:
                logger.warning(f"BANNED BLOCKED: {user.telegram_id}")

                if bot and isinstance(event, Message):
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text="🚫 You no longer have access."
                    )
                return None

        except Exception:
            logger.exception("BanMiddleware failure")
            if session:
                await session.rollback()
            return None

        return await handler(event, data)


# =========================
# RATE LIMITING (SMART)
# =========================
class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limiter: RateLimiter) -> None:
        self.limiter = limiter

    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("user")
        bot = data.get("bot")

        data.setdefault("rate_limiter", self.limiter)

        if not user:
            return await handler(event, data)

        try:
            event_type = event.__class__.__name__
            key = f"{event_type}:msg"

            allowed = await self.limiter.allow_user(
                user.telegram_id,
                key,
                limit=25,
                window_seconds=30,
            )

            if not allowed:
                logger.info(f"RATE LIMITED: {user.telegram_id}")

                if bot and isinstance(event, Message):
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text="⚠️ Slow down."
                    )
                return None

        except Exception:
            logger.exception("RateLimitMiddleware failure")
            return None

        return await handler(event, data)


# =========================
# SUBSCRIPTION / ACCESS CONTROL
# =========================
class SubscriptionMiddleware(BaseMiddleware):
    """
    Requires user to have active subscription or admin override.
    Attach this ONLY to protected routes.
    """

    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("user")
        profile = data.get("profile")
        bot = data.get("bot")

        if not user or not profile:
            return await handler(event, data)

        try:
            # Admin bypass
            if user.is_admin:
                return await handler(event, data)

            # 🔥 Customize this logic to match your Stripe system
            is_active = getattr(profile, "subscription_active", False)

            if not is_active:
                if bot and isinstance(event, Message):
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            "🔒 This feature is locked.\n\n"
                            "Upgrade to access elite tools."
                        ),
                    )
                return None

        except Exception:
            logger.exception("SubscriptionMiddleware failure")
            return None

        return await handler(event, data)
