from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import MessageRecord, Order, Referral, User
from ...repos.bans import BanRepository
from ...repos.users import UserRepository
from ...services.broadcast import BroadcastService
from ...services.rate_limit import RateLimiter
from ...utils.markdown import escape_markdown_v2

router = Router(name="admin")


def _ensure_admin(user: User) -> bool:
    return bool(user.is_admin)


@router.message(Command("admin"))
async def cmd_admin(message: Message, user: User) -> None:
    if not _ensure_admin(user):
        await message.answer("Not authorized.")
        return
    await message.answer("Admin commands: /stats, /broadcast, /ban, /unban")


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, user: User) -> None:
    if not _ensure_admin(user):
        await message.answer("Not authorized.")
        return
    total_users = await session.scalar(select(func.count()).select_from(User))
    total_orders = await session.scalar(select(func.count()).select_from(Order))
    total_referrals = await session.scalar(select(func.count()).select_from(Referral))
    total_messages = await session.scalar(select(func.count()).select_from(MessageRecord))
    text = (
        f"Users: {total_users}
"
        f"Orders: {total_orders}
"
        f"Referrals: {total_referrals}
"
        f"Messages logged: {total_messages}"
    )
    await message.answer(escape_markdown_v2(text))


@router.message(Command("broadcast"))
async def cmd_broadcast(
    message: Message,
    command: CommandObject | None,
    session: AsyncSession,
    user: User,
    rate_limiter: RateLimiter,
) -> None:
    if not _ensure_admin(user):
        await message.answer("Not authorized.")
        return
    if not command or not command.args:
        await message.answer("Usage: /broadcast <message>")
        return
    repo = UserRepository(session)
    service = BroadcastService(session=session, bot=message.bot, rate_limiter=rate_limiter, users=repo)
    user_ids = await repo.list_user_ids()
    summary = await service.send(user_ids, command.args)
    await message.answer(f"Broadcast sent: {summary.sent}, failed: {summary.failed}")


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject | None, session: AsyncSession, user: User) -> None:
    if not _ensure_admin(user):
        await message.answer("Not authorized.")
        return
    if not command or not command.args:
        await message.answer("Usage: /ban <telegram_id>")
        return
    try:
        target_id = int(command.args.strip())
    except ValueError:
        await message.answer("Invalid telegram ID")
        return
    repo = UserRepository(session)
    target = await repo.get_by_telegram_id(target_id)
    if not target:
        await message.answer("User not found")
        return
    bans = BanRepository(session)
    await bans.create_or_update(target.id, reason="Admin ban")
    await message.answer(f"User {target_id} banned.")


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject | None, session: AsyncSession, user: User) -> None:
    if not _ensure_admin(user):
        await message.answer("Not authorized.")
        return
    if not command or not command.args:
        await message.answer("Usage: /unban <telegram_id>")
        return
    try:
        target_id = int(command.args.strip())
    except ValueError:
        await message.answer("Invalid telegram ID")
        return
    repo = UserRepository(session)
    target = await repo.get_by_telegram_id(target_id)
    if not target:
        await message.answer("User not found")
        return
    bans = BanRepository(session)
    await bans.remove(target.id)
    await message.answer(f"User {target_id} unbanned.")
