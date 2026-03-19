from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import User
from ...services.payments import PaymentsService
from ...services.referrals import ReferralService
from ...utils.markdown import escape_markdown_v2
from ..keyboards import referral_keyboard, shop_keyboard

router = Router(name="base")


def command_aliases(*names: str) -> Command:
    return Command(commands=list(names))


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
        "Use /help to explore commands, /shop to browse products, and /account to view your profile."
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
        "/support — support contact",
        "",
        "🛍 *Products*",
        "/shop — browse products",
        "/products — live product list",
        "/buy <sku> — purchase",
        "",
        "🛠 *System*",
        "/webhookstatus — webhook health",
    ]

    if user.is_admin:
        commands.extend(
            [
                "",
                "🔐 *Admin*",
                "/admin — admin panel",
                "/addproduct — product config note",
                "/removeproduct — product config note",
                "/broadcast <message>",
                "/stats — system stats",
                "/users — user count",
            ]
        )

    text = "📖 *Available Commands*\n\n" + "\n".join(commands)
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(command_aliases("account", "profile"))
async def cmd_account(message: Message, user: User) -> None:
    username = escape_markdown_v2(user.first_name or user.username or str(user.telegram_id))
    referral_link = f"https://t.me/{settings.telegram_bot_username}?start={user.referral_code}"

    text = (
        "👤 *Account*\n\n"
        f"Name: {username}\n"
        f"Referral code: `{user.referral_code}`\n"
        f"Referral link: {escape_markdown_v2(referral_link)}\n"
        f"Referrals: *{user.referral_count}*\n"
        f"Admin: *{'yes' if user.is_admin else 'no'}*"
    )

    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=referral_keyboard(user.referral_code),
    )


@router.message(Command("support"))
async def cmd_support(message: Message) -> None:
    await message.answer("Support is available through the configured admin team. Use /help for guided flows.")


@router.message(command_aliases("shop", "products"))
async def cmd_shop(message: Message, session: AsyncSession) -> None:
    service = PaymentsService(session, bot=None)
    products = service.product_catalog()
    if not products:
        await message.answer("🛒 Store is temporarily unavailable. Stripe product pricing is not configured yet.")
        return

    lines = [f"• {product['title']} — `{product['sku']}` — {product['description']}" for product in products]
    text = "🛒 *Available Products*\n\n" + "\n".join(lines)
    await message.answer(
        escape_markdown_v2(text),
        parse_mode="MarkdownV2",
        reply_markup=shop_keyboard(products),
    )


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
