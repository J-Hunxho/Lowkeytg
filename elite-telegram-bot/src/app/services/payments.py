from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import stripe
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..logging import logger
from ..models import (
    AccessGrant,
    AdminSetting,
    Order,
    Product,
    Purchase,
    StripeEvent,
    StripePrice,
    StripeProduct,
    StripeSubscription,
    User,
)
from ..repos.orders import OrderRepository


class PaymentsService:
    def __init__(self, session, bot: Optional[Bot] = None) -> None:
        self.session = session
        self.orders = OrderRepository(session)
        self.bot = bot
        self.settings = get_settings()

        if self.settings.stripe_secret_key:
            stripe.api_key = self.settings.stripe_secret_key.get_secret_value()

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

    async def product_catalog(self) -> list[dict[str, Any]]:
        maintenance = await self.session.scalar(select(AdminSetting).where(AdminSetting.key == "maintenance_mode"))
        if maintenance and bool(maintenance.value):
            return []

        result = await self.session.execute(
            select(Product).where(Product.active.is_(True)).order_by(Product.featured.desc(), Product.sort_order.asc(), Product.id.asc())
        )
        rows = list(result.scalars())
        return [
            {
                "sku": product.sku,
                "title": product.title,
                "description": product.description or "",
                "price_id": product.stripe_price_id,
                "product_id": product.stripe_product_id,
                "currency": product.currency,
                "unit_amount": product.unit_amount,
                "recurring_interval": product.recurring_interval,
                "featured": product.featured,
                "category": product.telegram_category,
                "purchase_type": product.purchase_type,
                "button_label": product.button_label or "Buy now",
                "delivery_type": product.delivery_type,
                "access_role": product.access_role,
            }
            for product in rows
            if product.stripe_price_id
        ]


    def _legacy_sku_for_price(self, stripe_price_id: str | None) -> str | None:
        legacy = {
            self.settings.price_id_founder_key: "founder_key",
            self.settings.price_id_vip_month: "vip_month",
            self.settings.price_id_vip_year: "vip_year",
        }
        return legacy.get(stripe_price_id)

    async def sync_products_from_stripe(self) -> int:
        if not self.settings.stripe_secret_key:
            raise ValueError("Stripe not configured")

        products = await self._retry_blocking("stripe_list_products", stripe.Product.list, limit=100)
        prices = await self._retry_blocking("stripe_list_prices", stripe.Price.list, limit=100)

        product_map: dict[str, StripeProduct] = {}
        for sp in products.data:
            product_row = await self.session.scalar(select(StripeProduct).where(StripeProduct.stripe_product_id == sp.id))
            if product_row is None:
                product_row = StripeProduct(stripe_product_id=sp.id, name=sp.name)
                self.session.add(product_row)
            product_row.name = sp.name
            product_row.description = sp.description
            product_row.active = bool(sp.active)
            product_row.metadata_json = sp.metadata or {}
            product_map[sp.id] = product_row

        synced = 0
        for pr in prices.data:
            price_row = await self.session.scalar(select(StripePrice).where(StripePrice.stripe_price_id == pr.id))
            if price_row is None:
                price_row = StripePrice(stripe_price_id=pr.id, stripe_product_id=pr.product)
                self.session.add(price_row)

            price_row.stripe_product_id = pr.product
            price_row.currency = pr.currency
            price_row.unit_amount = pr.unit_amount
            price_row.recurring_interval = pr.recurring.interval if pr.recurring else None
            price_row.recurring_interval_count = pr.recurring.interval_count if pr.recurring else None
            price_row.type = pr.type
            price_row.active = bool(pr.active)
            price_row.metadata_json = pr.metadata or {}

            sp = products.data_map.get(pr.product) if hasattr(products, "data_map") else None
            if sp is None:
                sp = next((p for p in products.data if p.id == pr.product), None)
            if sp is None:
                continue

            forced_sku = self._legacy_sku_for_price(pr.id)
            await self._upsert_catalog_from_stripe(sp, pr, forced_sku=forced_sku)
            synced += 1

        await self.session.commit()
        return synced

    async def _upsert_catalog_from_stripe(self, stripe_product_obj: Any, stripe_price_obj: Any, forced_sku: str | None = None) -> Product:
        merged_meta = {**(stripe_product_obj.metadata or {}), **(stripe_price_obj.metadata or {})}

        slug = merged_meta.get("telegram_slug") or stripe_product_obj.id.replace("prod_", "")
        sku = forced_sku or merged_meta.get("sku") or slug

        product = await self.session.scalar(select(Product).where(Product.sku == sku))
        if product is None:
            product = Product(sku=sku, title=stripe_product_obj.name)
            self.session.add(product)

        product.stripe_product_id = stripe_product_obj.id
        product.stripe_price_id = stripe_price_obj.id
        product.title = stripe_product_obj.name
        product.description = stripe_product_obj.description
        product.currency = stripe_price_obj.currency
        product.unit_amount = stripe_price_obj.unit_amount
        product.recurring_interval = stripe_price_obj.recurring.interval if stripe_price_obj.recurring else None
        product.purchase_type = "recurring" if stripe_price_obj.recurring else (stripe_price_obj.type or "one_time")
        product.active = bool(stripe_product_obj.active and stripe_price_obj.active)
        product.featured = str(merged_meta.get("featured", "false")).lower() in {"1", "true", "yes"}
        product.telegram_slug = merged_meta.get("telegram_slug")
        product.telegram_category = merged_meta.get("telegram_category")
        product.delivery_type = merged_meta.get("delivery_type")
        product.access_role = merged_meta.get("access_role")
        product.channel_announcement = merged_meta.get("channel_announcement")
        product.button_label = merged_meta.get("button_label")
        try:
            product.sort_order = int(merged_meta.get("sort_order", product.sort_order or 0))
        except (TypeError, ValueError):
            product.sort_order = 0
        product.metadata_json = merged_meta
        return product

    async def create_checkout_session(
        self,
        user: User,
        sku: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        if not self.settings.stripe_secret_key:
            raise ValueError("Stripe not configured")

        price_id = await self._price_id_for_sku(sku)
        if not price_id:
            raise ValueError("SKU not available")

        metadata = {
            "user_id": str(user.id),
            "telegram_id": str(user.telegram_id),
            "telegram_user_id": str(user.telegram_id),
            "sku": sku,
        }

        product = await self.session.scalar(select(Product).where(Product.sku == sku))
        mode = "subscription" if product and product.purchase_type == "recurring" else "payment"
        checkout_session = await self._retry_blocking(
            "create_checkout_session",
            stripe.checkout.Session.create,
            mode=mode,
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

    async def handle_stripe_event(self, payload: dict[str, Any]) -> Optional[Order]:
        event_id = payload.get("id")
        event_type = payload.get("type")
        data_object = payload.get("data", {}).get("object", {})
        if not event_id or not event_type:
            return None

        existing = await self.session.scalar(select(StripeEvent).where(StripeEvent.event_id == event_id))
        if existing is not None:
            logger.info("stripe.event_duplicate", event_id=event_id, event_type=event_type)
            return None
        self.session.add(StripeEvent(event_id=event_id, event_type=event_type))

        order: Optional[Order] = None
        if event_type in {"product.created", "product.updated"}:
            await self._sync_single_product(data_object)
        elif event_type in {"price.created", "price.updated"}:
            await self._sync_single_price(data_object)
        elif event_type == "checkout.session.completed":
            order = await self._handle_checkout_completed(data_object)
        elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
            await self._handle_subscription_event(data_object)
        else:
            logger.info("stripe.event_ignored", event_type=event_type)

        await self.session.commit()
        return order

    async def _sync_single_product(self, stripe_product_obj: dict[str, Any]) -> None:
        product_id = stripe_product_obj.get("id")
        if not product_id:
            return

        product_row = await self.session.scalar(select(StripeProduct).where(StripeProduct.stripe_product_id == product_id))
        if product_row is None:
            product_row = StripeProduct(stripe_product_id=product_id, name=stripe_product_obj.get("name") or product_id)
            self.session.add(product_row)
        product_row.name = stripe_product_obj.get("name") or product_row.name
        product_row.description = stripe_product_obj.get("description")
        product_row.active = bool(stripe_product_obj.get("active", True))
        product_row.metadata_json = stripe_product_obj.get("metadata") or {}

        prices = await self._retry_blocking("stripe_list_prices_for_product", stripe.Price.list, product=product_id, limit=100)
        for price in prices.data:
            await self._sync_single_price(price.to_dict_recursive())

    async def _sync_single_price(self, stripe_price_obj: dict[str, Any]) -> None:
        price_id = stripe_price_obj.get("id")
        product_id = stripe_price_obj.get("product")
        if not price_id or not product_id:
            return

        price_row = await self.session.scalar(select(StripePrice).where(StripePrice.stripe_price_id == price_id))
        if price_row is None:
            price_row = StripePrice(stripe_price_id=price_id, stripe_product_id=product_id)
            self.session.add(price_row)

        recurring = stripe_price_obj.get("recurring") or {}
        price_row.stripe_product_id = product_id
        price_row.currency = stripe_price_obj.get("currency")
        price_row.unit_amount = stripe_price_obj.get("unit_amount")
        price_row.recurring_interval = recurring.get("interval")
        price_row.recurring_interval_count = recurring.get("interval_count")
        price_row.type = stripe_price_obj.get("type")
        price_row.active = bool(stripe_price_obj.get("active", True))
        price_row.metadata_json = stripe_price_obj.get("metadata") or {}

        product_row = await self.session.scalar(select(StripeProduct).where(StripeProduct.stripe_product_id == product_id))
        if product_row is None:
            stripe_product = await self._retry_blocking("stripe_retrieve_product", stripe.Product.retrieve, product_id)
            product_row = StripeProduct(
                stripe_product_id=product_id,
                name=stripe_product.name,
                description=stripe_product.description,
                active=bool(stripe_product.active),
                metadata_json=stripe_product.metadata or {},
            )
            self.session.add(product_row)

        forced_sku = self._legacy_sku_for_price(price_id)
        await self._upsert_catalog_from_stripe(product_row_to_obj(product_row), price_row_to_obj(price_row), forced_sku=forced_sku)

    async def _handle_checkout_completed(self, session_obj: dict[str, Any]) -> Optional[Order]:
        session_id = session_obj.get("id")
        payment_intent = session_obj.get("payment_intent")
        metadata = session_obj.get("metadata") or {}
        if not session_id:
            return None

        order = await self.orders.get_by_checkout_id(session_id)
        if order is None:
            logger.warning("stripe.checkout_without_order", checkout_id=session_id)
            return None

        line_items = await self._retry_blocking(
            "stripe_checkout_line_items",
            stripe.checkout.Session.list_line_items,
            session_id,
            limit=1,
        )
        first_item = line_items.data[0] if line_items.data else None
        price_id = first_item.price.id if first_item and first_item.price else None
        product_id = first_item.price.product if first_item and first_item.price else None

        if order.status != "paid":
            await self.orders.mark_paid(order, payment_intent or "")

        purchase = await self.session.scalar(select(Purchase).where(Purchase.stripe_checkout_id == session_id))
        if purchase is None:
            purchase = Purchase(user_id=order.user_id, order_id=order.id, stripe_checkout_id=session_id)
            self.session.add(purchase)
        purchase.stripe_payment_intent = payment_intent
        purchase.stripe_price_id = price_id
        purchase.stripe_product_id = product_id
        purchase.amount_total = session_obj.get("amount_total")
        purchase.currency = session_obj.get("currency")
        purchase.status = "paid"
        purchase.metadata_json = metadata

        await self._apply_delivery_hooks(order=order, metadata=metadata, product_id=product_id)
        await self._notify_user(order, "Payment received. Access has been unlocked.")
        await self._notify_admin_sale(order=order, amount=purchase.amount_total, currency=purchase.currency)
        return order

    async def _handle_subscription_event(self, sub_obj: dict[str, Any]) -> None:
        sub_id = sub_obj.get("id")
        if not sub_id:
            return

        status = sub_obj.get("status", "unknown")
        customer_id = sub_obj.get("customer")
        metadata = sub_obj.get("metadata") or {}
        item = ((sub_obj.get("items") or {}).get("data") or [{}])[0]
        price = item.get("price") or {}
        price_id = price.get("id")
        product_id = price.get("product")

        sub = await self.session.scalar(select(StripeSubscription).where(StripeSubscription.stripe_subscription_id == sub_id))
        if sub is None:
            sub = StripeSubscription(stripe_subscription_id=sub_id, status=status)
            self.session.add(sub)

        sub.status = status
        sub.stripe_customer_id = customer_id
        sub.stripe_price_id = price_id
        sub.stripe_product_id = product_id
        sub.cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end", False))
        cps = sub_obj.get("current_period_start")
        cpe = sub_obj.get("current_period_end")
        sub.current_period_start = datetime.fromtimestamp(cps, tz=timezone.utc) if cps else None
        sub.current_period_end = datetime.fromtimestamp(cpe, tz=timezone.utc) if cpe else None
        sub.metadata_json = metadata

        telegram_id = metadata.get("telegram_user_id") or metadata.get("telegram_id")
        if telegram_id and str(telegram_id).isdigit():
            user = await self.orders.get_user_by_telegram_id(int(telegram_id))
            if user:
                sub.user_id = user.id
                role = metadata.get("access_role") or f"sub:{product_id or 'unknown'}"
                grant = await self.session.scalar(
                    select(AccessGrant).where(AccessGrant.user_id == user.id, AccessGrant.sku == role)
                )
                if status in {"active", "trialing", "past_due"}:
                    if grant is None:
                        self.session.add(AccessGrant(user_id=user.id, order_id=None, sku=role, active=True))
                    else:
                        grant.active = True
                elif grant is not None:
                    grant.active = False

    async def _apply_delivery_hooks(self, order: Order, metadata: dict[str, Any], product_id: str | None) -> None:
        sku = metadata.get("access_role") or metadata.get("sku") or order.sku
        delivery_type = metadata.get("delivery_type") or "premium_commands"
        grant = await self.session.scalar(select(AccessGrant).where(AccessGrant.user_id == order.user_id, AccessGrant.sku == sku))
        if grant is None:
            self.session.add(AccessGrant(user_id=order.user_id, order_id=order.id, sku=sku, active=True))
        else:
            grant.active = True

        logger.info(
            "delivery.hook_applied",
            user_id=order.user_id,
            order_id=order.id,
            sku=sku,
            delivery_type=delivery_type,
            stripe_product_id=product_id,
        )

    async def _notify_admin_sale(self, order: Order, amount: int | None, currency: str | None) -> None:
        if not self.bot or not self.settings.notify_admin_on_sale:
            return
        if not self.settings.admin_user_ids:
            return

        text = (
            f"💰 New sale\n"
            f"Order: {order.id}\n"
            f"User: {order.user_id}\n"
            f"SKU: {order.sku}\n"
            f"Amount: {(amount or 0) / 100:.2f} {(currency or '').upper()}"
        )
        for admin_id in self.settings.admin_user_ids:
            try:
                await self.bot.send_message(chat_id=int(admin_id), text=text)
            except Exception as exc:
                logger.warning("admin.sale_notify_failed", admin_id=admin_id, error=str(exc))

    async def _notify_user(self, order: Order, message: str) -> None:
        if not self.bot:
            return

        metadata = order.extra_data or {}
        telegram_id = metadata.get("telegram_user_id") or metadata.get("telegram_id")
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

    async def _price_id_for_sku(self, sku: str) -> Optional[str]:
        product = await self.session.scalar(select(Product).where(Product.sku == sku, Product.active.is_(True)))
        return product.stripe_price_id if product and product.stripe_price_id else None


def product_row_to_obj(row: StripeProduct) -> Any:
    class Obj:
        pass

    obj = Obj()
    obj.id = row.stripe_product_id
    obj.name = row.name
    obj.description = row.description
    obj.active = row.active
    obj.metadata = row.metadata_json or {}
    return obj


def price_row_to_obj(row: StripePrice) -> Any:
    class Recurring:
        interval = None
        interval_count = None

    class Obj:
        pass

    obj = Obj()
    obj.id = row.stripe_price_id
    obj.product = row.stripe_product_id
    obj.currency = row.currency
    obj.unit_amount = row.unit_amount
    obj.type = row.type
    obj.active = row.active
    obj.metadata = row.metadata_json or {}
    rec = Recurring()
    rec.interval = row.recurring_interval
    rec.interval_count = row.recurring_interval_count
    obj.recurring = rec if row.recurring_interval else None
    return obj
