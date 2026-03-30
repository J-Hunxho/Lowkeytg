from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import User, UserStreak
from ...services.payments import PaymentsService
from ...services.referrals import ReferralService
from ...services.retention import RetentionService
from ...services.ai import AIService
from ...services.ai.service import AIQuotaExceeded, AIServiceDisabled
from ...utils.markdown import escape_markdown_v2
from ..keyboards import referral_keyboard, shop_keyboard

router = Router(name="base")


def command_aliases(*names: str) -> Command:
    return Command(commands=list(names))


def _format_catalog(products: list[dict[str, str]]) -> str:
    if not products:
        return "Access Drops are temporarily unavailable while pricing is being finalized."
    lines = [
        "• "
        f"{escape_markdown_v2(product['title'])} — `{escape_markdown_v2(product['sku'])}`\n  "
        f"{escape_markdown_v2(product['description'])}"
        for product in products
    ]
    return "🛍 *Access Drops*\n\n" + "\n".join(lines)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
) -> None:
    referral_code = command.args.strip() if command and command.args else None

    if referral_code:
        service = ReferralService(session)
        await service.process_referral(user, referral_code)

    name = escape_markdown_v2(user.first_name or user.username or "friend")
    text = (
        f"👋 Welcome, {name}.\n\n"
        "Lowkey is your private access layer for curated drops, member tiers, and concierge-grade support.\n\n"
        "Start with /plans, browse /shop, and open /app for the premium dashboard."
    )
    await message.answer(text, parse_mode="MarkdownV2")


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    commands = [
        "👤 *Member Surface*",
        "/start — private entry",
        "/shop — access drops",
        "/plans — membership tiers",
        "/account — account status",
        "/orders — order history",
        "/badges — member badges",
        "/leaderboard — referral leaderboard",
        "/support — concierge support",
        "/ai — AI concierge",
        "/app — launch mini app",
        "/buy <sku> — checkout by SKU",
        "",
        "🎯 *Growth*",
        "/referrals — referral performance",
    ]

    if user.is_admin:
        commands.extend(
            [
                "",
                "🔐 *Admin*",
                "/admin — admin panel",
                "/sync_products — sync Stripe catalog",
                "/reload_settings — check runtime env",
                "/broadcast_product <sku> — product campaign",
                "/broadcast <message> — send announcement",
                "/stats — system stats",
                "/users — user count",
                "/status — stack readiness",
                "/webhookstatus — webhook health",
            ]
        )

    text = "📖 *Available Commands*\n\n" + "\n".join(commands)
    await message.answer(text, parse_mode="MarkdownV2")


@router.message(command_aliases("account", "profile"))
async def cmd_account(message: Message, user: User, session: AsyncSession) -> None:
    username = escape_markdown_v2(user.first_name or user.username or str(user.telegram_id))
    referral_link = f"https://t.me/{settings.telegram_bot_username}?start={user.referral_code}"
    try:
        ai_status = await AIService(session).usage_snapshot(user)
    except AIServiceDisabled:
        ai_status = {"tier": "disabled", "used_today": 0, "daily_limit": 0}
    retention = RetentionService(session)
    badges = await retention.badges_for_user(user)
    streak = await session.scalar(select(UserStreak).where(UserStreak.user_id == user.id))
    badge_labels = ", ".join(badge.label for badge in badges[:3]) if badges else "No badges yet"

    text = (
        "👤 *Account*\n\n"
        f"Name: {username}\n"
        f"Referral code: `{user.referral_code}`\n"
        f"Referral link: {escape_markdown_v2(referral_link)}\n"
        f"Referrals: *{user.referral_count}*\n"
        f"Streak: *{streak.current_streak if streak else 0} day(s)*\n"
        f"Badges: *{escape_markdown_v2(badge_labels)}*\n"
        f"Admin: *{'yes' if user.is_admin else 'no'}*\n"
        f"AI tier: *{ai_status['tier']}* ({ai_status['used_today']}/{ai_status['daily_limit']} used)"
    )

    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=referral_keyboard(user.referral_code),
    )


@router.message(Command("referrals"))
async def cmd_referrals(message: Message, user: User) -> None:
    referral_link = f"https://t.me/{settings.telegram_bot_username}?start={user.referral_code}"
    text = (
        "🎯 *Referral Engine*\n\n"
        f"Code: `{user.referral_code}`\n"
        f"Shares: *{user.referral_count} successful joins*\n"
        f"Invite link: {escape_markdown_v2(referral_link)}"
    )
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(Command("badges"))
async def cmd_badges(message: Message, user: User, session: AsyncSession) -> None:
    service = RetentionService(session)
    badges = await service.badges_for_user(user)
    if not badges:
        await message.answer("🏅 No badges yet. Keep your streak active and refer new members.")
        return
    lines = [f"• *{escape_markdown_v2(item.label)}* — {escape_markdown_v2(item.detail or '')}" for item in badges]
    await message.answer("🏅 *Badges*\n\n" + "\n".join(lines), parse_mode="MarkdownV2")


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, session: AsyncSession) -> None:
    service = RetentionService(session)
    leaders = await service.referral_leaderboard(limit=10)
    lines = []
    for index, member in enumerate(leaders, start=1):
        handle = member.username or member.first_name or str(member.telegram_id)
        lines.append(f"{index}\\. {escape_markdown_v2(handle)} — *{member.referral_count}* referrals")
    text = "📈 *Referral Leaderboard*\n\n" + ("\n".join(lines) if lines else "No leaderboard data yet.")
    await message.answer(text, parse_mode="MarkdownV2")


@router.message(Command("support"))
async def cmd_support(message: Message) -> None:
    await message.answer(
        f"Support is handled by {settings.support_contact}. Share your SKU and issue summary for priority handling."
    )


@router.message(command_aliases("shop", "products"))
async def cmd_shop(message: Message, session: AsyncSession) -> None:
    service = PaymentsService(session, bot=None)
    products = await service.product_catalog()
    text = _format_catalog(products)
    if not products:
        await message.answer(text)
        return

    await message.answer(
        escape_markdown_v2(text),
        parse_mode="MarkdownV2",
        reply_markup=shop_keyboard(products),
    )


@router.message(command_aliases("plans", "pricing"))
async def cmd_pricing(message: Message, session: AsyncSession) -> None:
    service = PaymentsService(session, bot=None)
    products = await service.product_catalog()
    if not products:
        await message.answer("Pricing is not published yet. Configure Stripe price IDs to go live.")
        return

    lines = [
        f"• *{escape_markdown_v2(product['title'])}* — SKU `{escape_markdown_v2(product['sku'])}`\n  {escape_markdown_v2(product['description'])}"
        for product in products
    ]
    text = "💠 *Membership Tiers*\n\n" + "\n".join(lines) + "\n\nUse /buy <sku> for instant checkout."
    await message.answer(text, parse_mode="MarkdownV2")




@router.message(Command("ai"))
async def cmd_ai(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
) -> None:
    ai = AIService(session)
    prompt = command.args.strip() if command and command.args else ""
    try:
        status = await ai.usage_snapshot(user)
    except AIServiceDisabled:
        await message.answer("AI service is currently disabled by admin configuration.")
        return

    if not prompt:
        await message.answer(
            f"🤖 AI status\n\n"
            f"Tier: {status['tier']}\n"
            f"Provider: {status['provider']}\n"
            f"Model: {status['model']}\n"
            f"Used today: {status['used_today']}/{status['daily_limit']}\n\n"
            "Use /ai <your prompt> to run a request."
        )
        return

    try:
        result = await ai.respond(user=user, prompt=prompt)
        updated = await ai.usage_snapshot(user)
        await message.answer(
            f"🧠 {result['reply']}\n\n"
            f"Plan: {result['tier']} · Model: {result['model']}\n"
            f"Remaining today: {updated['remaining_today']}"
        )
    except AIQuotaExceeded:
        await message.answer(
            f"🚫 Daily AI quota exceeded for tier '{status['tier']}'. "
            f"Used {status['used_today']}/{status['daily_limit']} today."
        )
    except AIServiceDisabled:
        await message.answer("AI service is currently disabled by admin configuration.")

@router.message(Command("status"))
async def cmd_status(message: Message, session: AsyncSession) -> None:
    service = PaymentsService(session, bot=None)
    products = await service.product_catalog()
    try:
        mini_app_url = settings.mini_app_url
        public_url_status = f"online · {mini_app_url}"
    except RuntimeError:
        public_url_status = "offline · missing PUBLIC_BASE_URL"

    status_text = (
        "🧠 *Production Status*\n\n"
        f"Telegram: *{'enabled' if settings.telegram_enabled else 'disabled'}*\n"
        f"Stripe: *{'enabled' if settings.stripe_enabled else 'disabled'}*\n"
        f"Catalog size: *{len(products)} live SKU(s)*\n"
        f"Mini app: *{escape_markdown_v2(public_url_status)}*"
    )
    await message.answer(escape_markdown_v2(status_text), parse_mode="MarkdownV2")


@router.message(Command("webhookstatus"))
async def cmd_webhookstatus(message: Message) -> None:
    try:
        expected_url = settings.webhook_url
    except RuntimeError:
        await message.answer("Webhook base URL is not configured.")
        return

    info = await message.bot.get_webhook_info()
    configured = "yes" if info.url == expected_url else "no"
    text = (
        "🔌 *Webhook Status*\n\n"
        f"Expected: {escape_markdown_v2(expected_url)}\n"
        f"Actual: {escape_markdown_v2(info.url or 'not set')}\n"
        f"Configured: *{configured}*\n"
        f"Pending updates: *{info.pending_update_count}*"
    )
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    try:
        mini_app_url = settings.mini_app_url
    except RuntimeError:
        await message.answer("Mini app unavailable: configure PUBLIC_BASE_URL or Railway public URL first.")
        return

    await message.answer(
        "Open the Lowkey mini app:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Launch Mini App",
                        web_app=WebAppInfo(url=mini_app_url),
                    )
                ]
            ]
        ),
    )


@router.message(F.web_app_data)
async def on_webapp_data(message: Message) -> None:
    await message.answer(f"✅ Mini app payload received:\n{message.web_app_data.data}")


@router.message(F.text.startswith("/"))
async def cmd_fallback(message: Message) -> None:
    await message.answer("Unknown command forwarded to bot router. Use /help.")
