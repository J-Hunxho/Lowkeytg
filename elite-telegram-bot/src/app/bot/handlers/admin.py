from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import MessageRecord, Order, Referral, User
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
            "/stats — system stats\n"
            "/users — total users\n"
            "/broadcast <msg> — send announcement\n"
            "/addproduct — configure catalog via env\n"
            "/removeproduct — disable catalog via env\n"
            "/healthcheck — readiness report\n"
            "/catalogsync — inspect live SKUs\n"
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

    counts = await session.execute(
        select(
            func.count(User.id),
            func.count(Order.id),
            func.count(Referral.id),
            func.count(MessageRecord.id),
        )
        .select_from(User)
        .outerjoin(Order)
        .outerjoin(Referral)
        .outerjoin(MessageRecord)
    )

    users, orders, referrals, messages = counts.one()
    text = (
        "📊 *System Stats*\n"
        f"Users: `{users}`\n"
        f"Orders: `{orders}`\n"
        f"Referrals: `{referrals}`\n"
        f"Messages logged: `{messages}`"
    )
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(Command("healthcheck"))
async def cmd_healthcheck(message: Message, session: AsyncSession, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    service = PaymentsService(session, bot=None)
    products = service.product_catalog()
    checklist = [
        f"Telegram enabled: {'yes' if settings.telegram_enabled else 'no'}",
        f"Stripe enabled: {'yes' if settings.stripe_enabled else 'no'}",
        f"Webhook auto-sync: {'yes' if settings.set_webhook_on_start else 'no'}",
        f"Fail-fast startup: {'yes' if settings.fail_fast_on_startup else 'no'}",
        f"Catalog SKU count: {len(products)}",
        f"Public base URL configured: {'yes' if bool(settings.public_base_url or settings.railway_static_url or settings.railway_public_domain) else 'no'}",
    ]
    text = "🩺 *Production Readiness*\n\n" + "\n".join(f"• {item}" for item in checklist)
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(Command("catalogsync"))
async def cmd_catalogsync(message: Message, session: AsyncSession, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    service = PaymentsService(session, bot=None)
    products = service.product_catalog()
    if not products:
        await message.answer("Catalog is empty. Add Stripe price IDs and redeploy.")
        return

    lines = [f"• {product['sku']} -> {product['price_id']}" for product in products]
    text = "🧾 *Catalog Sync*\n\n" + "\n".join(lines)
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


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


@router.message(Command("addproduct"))
async def cmd_addproduct(message: Message, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    await message.answer("Products are env-driven. Add a Stripe price env var and redeploy to publish it.")


@router.message(Command("removeproduct"))
async def cmd_removeproduct(message: Message, user: User) -> None:
    try:
        _ensure_admin(user)
    except PermissionError:
        await _not_authorized(message)
        return

    await message.answer("Remove the related Stripe price env var and redeploy to unpublish the product.")
