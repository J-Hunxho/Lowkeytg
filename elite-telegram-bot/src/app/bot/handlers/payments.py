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


async def _create_checkout(*, user: User, session: AsyncSession, sku: str) -> Optional[str]:
    if not settings.stripe_secret_key:
        return None

    try:
        success_url = settings.join_public_url("/payments/success")
        cancel_url = settings.join_public_url("/payments/cancel")
    except RuntimeError:
        return None

    service = PaymentsService(session, bot=None)

    try:
        checkout = await service.create_checkout_session(
            user=user,
            sku=sku,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return checkout["url"]
    except ValueError:
        return None


@router.message(Command("buy"))
async def cmd_buy(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
) -> None:
    sku = command.args.strip() if command and command.args else ""
    if not sku:
        await message.answer("Usage: /buy <sku>")
        return

    await message.answer("💳 Preparing checkout…")

    url = await _create_checkout(user=user, session=session, sku=sku)
    if not url:
        await message.answer(
            "❌ Checkout unavailable.\nEnsure the SKU exists, PUBLIC_BASE_URL is valid, and Stripe is configured."
        )
        return

    await message.answer(
        escape_markdown_v2("✅ *Checkout ready*"),
        parse_mode="MarkdownV2",
        reply_markup=checkout_keyboard(url),
    )


@router.callback_query(lambda q: q.data and q.data.startswith("buy:"))
async def cb_buy(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
) -> None:
    _, sku = callback.data.split(":", 1)

    url = await _create_checkout(user=user, session=session, sku=sku)
    if not url:
        await callback.answer("Checkout unavailable.", show_alert=True)
        return

    await callback.message.answer(
        escape_markdown_v2("✅ *Checkout ready*"),
        parse_mode="MarkdownV2",
        reply_markup=checkout_keyboard(url),
    )
    await callback.answer()


@router.message(Command("orders"))
async def cmd_orders(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    service = PaymentsService(session, bot=None)
    orders = await service.orders.list_for_user(user.id)

    if not orders:
        await message.answer("📭 No orders yet.")
        return

    lines = [f"• `{order.sku}` — *{order.status}*" for order in orders]

    text = "📦 *Your Orders*\n\n" + "\n".join(lines)

    await message.answer(
        escape_markdown_v2(text),
        parse_mode="MarkdownV2",
    )
