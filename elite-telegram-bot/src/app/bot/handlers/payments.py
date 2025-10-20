from __future__ import annotations

from typing import Optional

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import User
from ...services.payments import PaymentsService
from ...utils.markdown import escape_markdown_v2
from ..keyboards import checkout_keyboard

router = Router(name="payments")


async def _create_checkout(user: User, session: AsyncSession, sku: str) -> Optional[dict]:
    if not settings.stripe_secret_key:
        return None
    service = PaymentsService(session, bot=None)
    success_url = f"{settings.public_base_url}/payments/success"
    cancel_url = f"{settings.public_base_url}/payments/cancel"
    try:
        return await service.create_checkout_session(
            user=user,
            sku=sku,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError:
        return None


@router.message(Command("buy"))
async def cmd_buy(message: Message, command: CommandObject | None, session: AsyncSession, user: User) -> None:
    sku = command.args.strip() if command and command.args else ""
    if not sku:
        await message.answer("Provide a SKU. Usage: /buy <sku>")
        return
    checkout = await _create_checkout(user, session, sku)
    if not checkout:
        await message.answer("Checkout unavailable. Ensure Stripe keys are configured.")
        return
    await message.answer(
        text=escape_markdown_v2("Checkout ready."),
        parse_mode="MarkdownV2",
        reply_markup=checkout_keyboard(checkout["url"]),
    )


@router.callback_query(lambda q: q.data and q.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer("Invalid request", show_alert=True)
        return
    sku = callback.data.split(":", 1)[1]
    checkout = await _create_checkout(user, session, sku)
    if not checkout:
        await callback.answer("Checkout unavailable", show_alert=True)
        return
    await callback.message.answer(
        text="Checkout ready.",
        reply_markup=checkout_keyboard(checkout["url"]),
    )
    await callback.answer()


@router.message(Command("orders"))
async def cmd_orders(message: Message, session: AsyncSession, user: User) -> None:
    service = PaymentsService(session, bot=None)
    orders = await service.orders.list_for_user(user.id)
    if not orders:
        await message.answer("No orders yet.")
        return
    lines = [f"• {order.sku} — {order.status}" for order in orders]
    await message.answer(escape_markdown_v2("\n".join(lines)), parse_mode="MarkdownV2")
