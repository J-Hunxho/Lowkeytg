from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import User
from ...services.referrals import ReferralService
from ...utils.markdown import escape_markdown_v2
from ..keyboards import referral_keyboard, shop_keyboard

router = Router(name="base")


# -------------------------
# /start
# -------------------------

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
        "Use /help to explore available commands."
    )

    await message.answer(text, parse_mode="MarkdownV2")


# -------------------------
# /help
# -------------------------

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


# -------------------------
# /ping
# -------------------------

@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    await message.answer("🏓 PONG")


# -------------------------
# /about
# -------------------------

@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    about = (
        "🤖 *LowkeyTG*\n\n"
        "Elite Telegram bot engineered by *Hunxho Codex*.\n"
        "Built with aiogram, FastAPI, and Stripe Checkout."
    )
    await message.answer(escape_markdown_v2(about), parse_mode="MarkdownV2")


# -------------------------
# /profile
# -------------------------

@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User) -> None:
    username = escape_markdown_v2(
        user.first_name or user.username or str(user.telegram_id)
    )

    referral_link = (
        f"https://t.me/{settings.telegram_bot_username}"
        f"?start={user.referral_code}"
    )

    text = (
        f"👤 *Profile*\n\n"
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


# -------------------------
# /shop
# -------------------------

@router.message(Command("shop"))
async def cmd_shop(message: Message) -> None:
    await message.answer(
        "🛒 *Select a product:*",
        parse_mode="MarkdownV2",
        reply_markup=shop_keyboard(),
    )
