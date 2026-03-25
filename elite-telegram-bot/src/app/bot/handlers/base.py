from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import User
from ...services.payments import PaymentsService
from ...services.referrals import ReferralService
from ...services.ai import AIService
from ...services.ai.service import AIQuotaExceeded, AIServiceDisabled
from ...utils.markdown import escape_markdown_v2
from ..keyboards import referral_keyboard, shop_keyboard

router = Router(name="base")


def command_aliases(*names: str) -> Command:
    return Command(commands=list(names))


def _format_catalog(products: list[dict[str, str]]) -> str:
    if not products:
        return "🛒 Store is temporarily unavailable. Stripe product pricing is not configured yet."
    lines = [f"• {product['title']} — `{product['sku']}` — {product['description']}" for product in products]
    return "🛒 *Available Products*\n\n" + "\n".join(lines)


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
        f"👋 Welcome, {name}!\n\n"
        "Use /help to explore commands, /shop to browse products, /plans to compare offers, and /account to view your profile."
    )
    await message.answer(text, parse_mode="MarkdownV2")


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    commands = [
        "👤 *User*",
        "/start — onboarding flow",
        "/help — command list",
        "/account — account overview",
        "/orders — order history",
        "/plans — compare plans",
        "/referrals — referral performance",
        "/support — support contact",
        "",
        "🛍 *Products*",
        "/shop — browse products",
        "/products — live product list",
        "/buy <sku> — purchase",
        "/app — launch mini app",
        "",
        "🛠 *System*",
        "/status — stack readiness summary",
        "/webhookstatus — webhook health",
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
                "/broadcast <message>",
                "/stats — system stats",
                "/users — user count",
            ]
        )

    text = "📖 *Available Commands*\n\n" + "\n".join(commands)
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(command_aliases("account", "profile"))
async def cmd_account(message: Message, user: User, session: AsyncSession) -> None:
    username = escape_markdown_v2(user.first_name or user.username or str(user.telegram_id))
    referral_link = f"https://t.me/{settings.telegram_bot_username}?start={user.referral_code}"
    try:
        ai_status = await AIService(session).usage_snapshot(user)
    except AIServiceDisabled:
        ai_status = {"tier": "disabled", "used_today": 0, "daily_limit": 0}

    text = (
        "👤 *Account*\n\n"
        f"Name: {username}\n"
        f"Referral code: `{user.referral_code}`\n"
        f"Referral link: {escape_markdown_v2(referral_link)}\n"
        f"Referrals: *{user.referral_count}*\n"
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


@router.message(Command("support"))
async def cmd_support(message: Message) -> None:
    await message.answer(
        f"Support is handled by {settings.support_contact}. Use /status before opening a ticket so the team gets context fast."
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
        f"• *{product['title']}* — SKU `{product['sku']}`\n  {product['description']}"
        for product in products
    ]
    text = "💠 *Pricing Overview*\n\n" + "\n".join(lines) + "\n\nUse /buy <sku> to start checkout instantly."
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")




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
