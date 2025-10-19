from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **kwargs: object) -> Order:
        order = Order(**kwargs)
        self.session.add(order)
        return order

    async def get_by_checkout_id(self, checkout_id: str) -> Optional[Order]:
        result = await self.session.execute(select(Order).where(Order.stripe_checkout_id == checkout_id))
        return result.scalars().first()

    async def list_for_user(self, user_id: int) -> List[Order]:
        result = await self.session.execute(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        )
        return list(result.scalars())

    async def mark_paid(self, order: Order, payment_intent: str) -> None:
        order.status = "paid"
        order.stripe_payment_intent = payment_intent
        order.paid_at = datetime.now(timezone.utc)

    async def mark_failed(self, order: Order) -> None:
        order.status = "failed"
