from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...logging import logger
from ...models import MessageRecord, Order, Product, Referral, User
from ...repos.bans import BanRepository
from ...repos.users import UserRepository
from ...services.broadcast import BroadcastService
from ...services.payments import PaymentsService
from ...services.rate_limit import RateLimiter
from ...utils.markdown import escape_markdown_v2

router = Router(name="admin")


def _ensure_admin(user: User) -> None:
    if not user.is_admin:
        raise PermissionError


async def _not_authorized(message: Message) -> None:
    await message.answer("🚫 Not authorized.")


@router.message(Command("admin"))
async def cmd_admin(message: Message, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    await message.answer(
        escape_markdown_v2(
            "🛠 *Admin Commands*\n"
            "/sync_products — sync Stripe products\n"
            "/reload_settings — confirm runtime settings\n"
            "/broadcast_product <sku> — blast one product\n"
            "/broadcast <msg> — send announcement\n"
            "/stats — system stats\n"
            "/users — total users\n"
            "/ban <telegram_id> [reason]\n"
            "/unban <telegram_id>"
        ),
        parse_mode="MarkdownV2",
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    users = await session.scalar(select(func.count(User.id)))
    orders = await session.scalar(select(func.count(Order.id)))
    referrals = await session.scalar(select(func.count(Referral.id)))
    messages = await session.scalar(select(func.count(MessageRecord.id)))

    text = (
        "📊 *System Stats*\n"
        f"Users: `{int(users or 0)}`\n"
        f"Orders: `{int(orders or 0)}`\n"
        f"Referrals: `{int(referrals or 0)}`\n"
        f"Messages logged: `{int(messages or 0)}`"
    )
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(Command("reload_settings"))
async def cmd_reload_settings(message: Message, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    checks = [
        f"telegram_enabled={settings.telegram_enabled}",
        f"stripe_enabled={settings.stripe_enabled}",
        f"set_webhook_on_start={settings.set_webhook_on_start}",
        f"webhook_path={settings.webhook_path}",
        f"admin_count={len(settings.admin_user_ids)}",
    ]
    await message.answer("✅ Runtime settings loaded:\n" + "\n".join(checks))


@router.message(Command("sync_products"))
@router.message(Command("catalogsync"))
async def cmd_sync_products(message: Message, session: AsyncSession, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    service = PaymentsService(session, bot=None)
    try:
        synced = await service.sync_products_from_stripe()
    except Exception as exc:
        logger.exception("admin.sync_products_failed", error=str(exc), admin=user.telegram_id)
        await message.answer("Sync failed. Verify Stripe credentials and network access.")
        return

    products = await service.product_catalog()
    lines = [f"• {product['sku']} → {product['price_id']}" for product in products[:20]]
    text = f"🧾 *Catalog Sync*\n\nSynced: *{synced}*\n" + "\n".join(lines)
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(Command("broadcast_product"))
async def cmd_broadcast_product(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
    rate_limiter: RateLimiter,
) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    sku = command.args.strip() if command and command.args else ""
    if not sku:
        await message.answer("Usage: /broadcast_product <sku>")
        return

    product = await session.scalar(select(Product).where(Product.sku == sku, Product.active.is_(True)))
    if product is None:
        await message.answer("Product not found or inactive.")
        return

    text = (
        f"🔥 New offer: {product.title}\n"
        f"SKU: {product.sku}\n"
        f"{product.description or 'Tap /shop to view details and purchase.'}"
    )

    repo = UserRepository(session)
    service = BroadcastService(
        session=session,
        bot=message.bot,
        rate_limiter=rate_limiter,
        users=repo,
        concurrency=10,
    )
    await message.answer("📣 Broadcasting product…")
    summary = await service.send(await repo.list_user_ids(), text)
    await message.answer(f"✅ Product broadcast done. Sent={summary.sent} Failed={summary.failed}")


@router.message(Command("broadcast"))
async def cmd_broadcast(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
    rate_limiter: RateLimiter,
) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    if not command or not command.args:
        await message.answer("Usage: /broadcast <message>")
        return

    text = command.args.strip()
    if len(text) > 4000:
        await message.answer("❌ Message too long (max 4000 chars).")
        return

    repo = UserRepository(session)
    service = BroadcastService(
        session=session,
        bot=message.bot,
        rate_limiter=rate_limiter,
        users=repo,
        concurrency=10,
    )

    await message.answer("📣 Broadcasting…")
    summary = await service.send(await repo.list_user_ids(), text)
    await message.answer(
        escape_markdown_v2(
            f"✅ *Broadcast Complete*\nSent: `{summary.sent}`\nFailed: `{summary.failed}`"
        ),
        parse_mode="MarkdownV2",
    )


@router.message(Command("ban"))
async def cmd_ban(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    if not command or not command.args:
        await message.answer("Usage: /ban <telegram_id> [reason]")
        return

    target, *reason_parts = command.args.split()
    if not target.isdigit():
        await message.answer("telegram_id must be numeric")
        return

    users = UserRepository(session)
    target_user = await users.get_by_telegram_id(int(target))
    if target_user is None:
        await message.answer("User not found")
        return

    bans = BanRepository(session)
    await bans.create_or_update(target_user.id, reason=" ".join(reason_parts) or None)
    await session.commit()
    await message.answer(f"✅ Banned {target_user.telegram_id}")


@router.message(Command("unban"))
async def cmd_unban(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    if not command or not command.args or not command.args.strip().isdigit():
        await message.answer("Usage: /unban <telegram_id>")
        return

    users = UserRepository(session)
    target_user = await users.get_by_telegram_id(int(command.args.strip()))
    if target_user is None:
        await message.answer("User not found")
        return

    bans = BanRepository(session)
    await bans.remove(target_user.id)
    await session.commit()
    await message.answer(f"✅ Unbanned {target_user.telegram_id}")


@router.message(Command("users"))
async def cmd_users(message: Message, session: AsyncSession, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    total = await session.scalar(select(func.count(User.id)))
    await message.answer(f"👥 Total users: {int(total or 0)}")
