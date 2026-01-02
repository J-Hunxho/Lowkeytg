from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import stripe
from aiogram import Bot

from ..config import get_settings
from ..models import Order, User
from ..repos.orders import OrderRepository


class PaymentsService:
    def __init__(self, session, bot: Optional[Bot] = None) -> None:
        self.session = session
        self.orders = OrderRepository(session)
        self.bot = bot

        # Lazy, cached settings (safe at runtime)
        self.settings = get_settings()

        # Configure Stripe only if available
        if self.settings.stripe_secret_key:
            stripe.api_key = self.settings.stripe_secret_key.get_secret_value()

    async def create_checkout_session(
        self,
        user: User,
        sku: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
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

        checkout_session = await asyncio.to_thread(
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
            metadata=metadata,
            status="pending",
        )

        return {
            "url": checkout_session["url"],
            "session_id": checkout_session["id"],
        }

    async def handle_checkout_event(
        self, payload: Dict[str, Any]
    ) -> Optional[Order]:
        event_type = payload.get("type")
        data_object = payload.get("data", {}).get("object", {})
        session_id = data_object.get("id")
        payment_intent = data_object.get("payment_intent")

        if not session_id:
            return None

        order = await self.orders.get_by_checkout_id(session_id)
        if not order:
            return None

        if event_type == "checkout.session.completed" and payment_intent:
            if order.status != "paid":
                await self.orders.mark_paid(order, payment_intent)
                await self._notify_user(order, "Payment received. Thank you!")
        elif event_type in {
            "checkout.session.expired",
            "checkout.session.async_payment_failed",
        }:
            await self.orders.mark_failed(order)
            await self._notify_user(
                order, "Payment failed or expired. Please try again."
            )

        return order

    async def _notify_user(self, order: Order, message: str) -> None:
        if not self.bot:
            return

        telegram_id = (
            order.metadata.get("telegram_id") if order.metadata else None
        )
        if not telegram_id:
            return

        await self.bot.send_message(
            chat_id=int(telegram_id),
            text=message,
        )

    def _price_id_for_sku(self, sku: str) -> Optional[str]:
        mapping = {
            "founder_key": self.settings.price_id_founder_key,
            "vip_month": self.settings.price_id_vip_month,
            "vip_year": self.settings.price_id_vip_year,
        }
        return mapping.get(sku)

