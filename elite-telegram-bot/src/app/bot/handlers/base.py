from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import User
from ...services.referrals import ReferralService
from ...utils.markdown import escape_markdown_v2
from ..keyboards import referral_keyboard, shop_keyboard

router = Router(name="base")


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
    text = f"👋 Welcome, {name}!\n\nUse /help to explore available commands."
    await message.answer(text, parse_mode="MarkdownV2")


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    commands = [
        "/start — restart bot",
        "/help — command list",
        "/profile — your account",
        "/ping — health check",
        "/about — bot info",
        "/shop — browse products",
        "/buy <sku> — purchase",
        "/orders — order history",
        "/app — open mini app",
    ]

    if user.is_admin:
        commands.extend(
            [
                "",
                "🔐 *Admin*",
                "/admin",
                "/stats",
                "/broadcast <message>",
                "/ban <telegram_id>",
                "/unban <telegram_id>",
            ]
        )

    text = "📖 *Available Commands*\n\n" + "\n".join(commands)
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    await message.answer("🏓 PONG")


@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    about = (
        "🤖 *LowkeyTG*\n\n"
        "Elite Telegram bot engineered by *Hunxho Codex*.\n"
        "Built with aiogram, FastAPI, and Stripe Checkout."
    )
    await message.answer(escape_markdown_v2(about), parse_mode="MarkdownV2")


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User) -> None:
    username = escape_markdown_v2(user.first_name or user.username or str(user.telegram_id))
    referral_link = f"https://t.me/{settings.telegram_bot_username}?start={user.referral_code}"

    text = (
        "👤 *Profile*\n\n"
        f"Name: {username}\n"
        f"Referral code: `{user.referral_code}`\n"
        f"Referral link: {escape_markdown_v2(referral_link)}\n"
        f"Referrals: *{user.referral_count}*"
    )

    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=referral_keyboard(user.referral_code),
    )


@router.message(Command("shop"))
async def cmd_shop(message: Message) -> None:
    await message.answer(
        "🛒 *Select a product:*",
        parse_mode="MarkdownV2",
        reply_markup=shop_keyboard(),
    )


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    if not settings.public_base_url:
        await message.answer("Mini app unavailable: set PUBLIC_BASE_URL first.")
        return

    await message.answer(
        "Open the Lowkey mini app:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Launch Mini App",
                        web_app=WebAppInfo(url=f"{settings.public_base_url}/mini-app"),
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
