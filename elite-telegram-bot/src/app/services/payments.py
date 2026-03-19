from __future__ import annotations

import asyncio
from typing import Any, Optional

import stripe
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..logging import logger
from ..models import Order, User
from ..repos.orders import OrderRepository


class PaymentsService:
    def __init__(self, session, bot: Optional[Bot] = None) -> None:
        self.session = session
        self.orders = OrderRepository(session)
        self.bot = bot
        self.settings = get_settings()

        if self.settings.stripe_secret_key:
            stripe.api_key = self.settings.stripe_secret_key.get_secret_value()

    def product_catalog(self) -> list[dict[str, str]]:
        catalog = [
            {
                "sku": "founder_key",
                "title": "Founder Key",
                "description": "Lifetime access drop.",
                "price_id": self.settings.price_id_founder_key,
            },
            {
                "sku": "vip_month",
                "title": "VIP Monthly",
                "description": "30-day premium tier.",
                "price_id": self.settings.price_id_vip_month,
            },
            {
                "sku": "vip_year",
                "title": "VIP Annual",
                "description": "365-day premium tier.",
                "price_id": self.settings.price_id_vip_year,
            },
        ]
        return [product for product in catalog if product["price_id"]]

    async def _retry_blocking(self, operation: str, func, *args, **kwargs) -> Any:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((stripe.error.APIConnectionError, stripe.error.APIError)),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            stop=stop_after_attempt(3),
            reraise=True,
        ):
            with attempt:
                logger.info("stripe.operation_attempt", operation=operation, attempt=attempt.retry_state.attempt_number)
                return await asyncio.to_thread(func, *args, **kwargs)

    async def create_checkout_session(
        self,
        user: User,
        sku: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        if not self.settings.stripe_secret_key:
            raise ValueError("Stripe not configured")

        price_id = self._price_id_for_sku(sku)
        if not price_id:
            raise ValueError("SKU not available")

        metadata = {
            "user_id": str(user.id),
            "telegram_id": str(user.telegram_id),
            "sku": sku,
        }

        checkout_session = await self._retry_blocking(
            "create_checkout_session",
            stripe.checkout.Session.create,
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(user.telegram_id),
            metadata=metadata,
        )

        await self.orders.create(
            user_id=user.id,
            sku=sku,
            price_id=price_id,
            stripe_checkout_id=checkout_session["id"],
            extra_data=metadata,
            status="pending",
        )
        await self.session.commit()

        return {
            "url": checkout_session["url"],
            "session_id": checkout_session["id"],
        }

    async def handle_checkout_event(self, payload: dict[str, Any]) -> Optional[Order]:
        event_type = payload.get("type")
        data_object = payload.get("data", {}).get("object", {})
        session_id = data_object.get("id")
        payment_intent = data_object.get("payment_intent")

        if not session_id:
            return None

        order = await self.orders.get_by_checkout_id(session_id)
        if not order:
            logger.warning("stripe.order_missing", checkout_id=session_id, event_type=event_type)
            return None

        if event_type == "checkout.session.completed" and payment_intent:
            if order.status != "paid":
                await self.orders.mark_paid(order, payment_intent)
                await self.session.commit()
                await self._notify_user(order, "Payment received. Your digital product is ready.")
        elif event_type in {"checkout.session.expired", "checkout.session.async_payment_failed"}:
            await self.orders.mark_failed(order)
            await self.session.commit()
            await self._notify_user(order, "Payment failed or expired. Please try again.")

        return order

    async def _notify_user(self, order: Order, message: str) -> None:
        if not self.bot:
            return

        metadata = order.extra_data or {}
        telegram_id = metadata.get("telegram_id")
        if not telegram_id:
            return

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(TelegramAPIError),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            stop=stop_after_attempt(3),
            reraise=True,
        ):
            with attempt:
                await self.bot.send_message(chat_id=int(telegram_id), text=message)

    def _price_id_for_sku(self, sku: str) -> Optional[str]:
        mapping = {product["sku"]: product["price_id"] for product in self.product_catalog()}
        return mapping.get(sku)
