from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...logging import logger
from ...models import User
from ...services.payments import PaymentsService
from ...utils.markdown import escape_markdown_v2
from ..keyboards import checkout_keyboard, product_detail_keyboard, shop_keyboard

router = Router(name="payments")


async def _create_checkout(*, user: User, session: AsyncSession, sku: str) -> str | None:
    if not settings.stripe_secret_key:
        logger.warning("checkout.unavailable", reason="stripe_secret_missing", sku=sku)
        return None

    try:
        success_url = settings.join_public_url("/payments/success")
        cancel_url = settings.join_public_url("/payments/cancel")
    except RuntimeError:
        logger.warning("checkout.unavailable", reason="public_base_url_missing", sku=sku)
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
    except ValueError as exc:
        logger.warning("checkout.unavailable", reason=str(exc), sku=sku, telegram_id=user.telegram_id)
        return None


async def _show_catalog(target: Message | CallbackQuery, session: AsyncSession) -> None:
    service = PaymentsService(session, bot=None)
    products = await service.product_catalog()
    if not products:
        text = "🛒 Catalog is empty. Sync Stripe products via /sync_products first."
        if isinstance(target, CallbackQuery):
            await target.message.answer(text)
        else:
            await target.answer(text)
        return

    lines = [f"• {p['title']} — `{p['sku']}`" for p in products]
    text = "🛍 *Catalog*\n\n" + "\n".join(lines)
    if isinstance(target, CallbackQuery):
        await target.message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2", reply_markup=shop_keyboard(products))
    else:
        await target.answer(escape_markdown_v2(text), parse_mode="MarkdownV2", reply_markup=shop_keyboard(products))


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
            "❌ Checkout unavailable. Ensure the SKU exists and Stripe/public URL settings are correct."
        )
        return

    await message.answer(
        escape_markdown_v2("✅ *Checkout ready*"),
        parse_mode="MarkdownV2",
        reply_markup=checkout_keyboard(url),
    )


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
) -> None:
    if not callback.data or ":" not in callback.data:
        await callback.answer("Invalid checkout request.", show_alert=True)
        return
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


@router.callback_query(F.data == "catalog:refresh")
async def cb_refresh_catalog(callback: CallbackQuery, session: AsyncSession) -> None:
    await _show_catalog(callback, session)
    await callback.answer("Catalog refreshed")


@router.callback_query(F.data.startswith("product:view:"))
async def cb_product_view(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data or callback.data.count(":") < 2:
        await callback.answer("Invalid product action", show_alert=True)
        return
    sku = callback.data.split(":", 2)[2]
    service = PaymentsService(session, bot=None)
    products = await service.product_catalog()
    product = next((p for p in products if p["sku"] == sku), None)
    if not product:
        await callback.answer("Product not found", show_alert=True)
        return

    checkout_url = await _create_checkout(user=user, session=session, sku=sku)
    text = (
        f"🧾 *{product['title']}*\n"
        f"SKU: `{product['sku']}`\n"
        f"{product.get('description') or 'No description'}"
    )
    await callback.message.answer(
        escape_markdown_v2(text),
        parse_mode="MarkdownV2",
        reply_markup=product_detail_keyboard(sku, checkout_url),
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