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


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
) -> None:
    referral_code = command.args if command else None
    service = ReferralService(session)
    await service.process_referral(user, referral_code)

    display_name = escape_markdown_v2(user.first_name or user.username or "friend")
    welcome = (
        f"Welcome, {display_name}!\n"
        "Use /help to explore commands."
    )
    await message.answer(welcome, parse_mode="MarkdownV2")


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    commands = [
        "/start",
        "/help",
        "/profile",
        "/ping",
        "/about",
        "/shop",
        "/buy <sku>",
        "/orders",
    ]
    if user.is_admin:
        commands.extend([
            "/admin",
            "/stats",
            "/broadcast <message>",
            "/ban <user_id>",
            "/unban <user_id>",
        ])
    text = "Available commands:\n" + "\n".join(commands)
    await message.answer(escape_markdown_v2(text), parse_mode="MarkdownV2")


@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    await message.answer("PONG")


@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    about = (
        "Elite Telegram bot crafted by Hunxho Codex Engineering.\n"
        "Powered by aiogram, FastAPI, and Stripe Checkout."
    )
    await message.answer(escape_markdown_v2(about), parse_mode="MarkdownV2")


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User) -> None:
    link = f"https://t.me/{settings.telegram_bot_username}?start={user.referral_code}"
    text = (
        f"👤 Profile for {escape_markdown_v2(user.first_name or user.username or str(user.telegram_id))}\n"
        f"Referral code: `{escape_markdown_v2(user.referral_code)}`\n"
        f"Referral link: {escape_markdown_v2(link)}\n"
        f"Referrals: *{user.referral_count}*"
    )
    await message.answer(text, parse_mode="MarkdownV2", reply_markup=referral_keyboard(user.referral_code))


@router.message(Command("shop"))
async def cmd_shop(message: Message) -> None:
    await message.answer("Select a product:", reply_markup=shop_keyboard())
