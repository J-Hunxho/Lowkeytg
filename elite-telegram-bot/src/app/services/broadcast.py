from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MessageRecord
from ..repos.users import UserRepository
from ..services.rate_limit import RateLimiter


@dataclass
class BroadcastSummary:
    sent: int
    failed: int


class BroadcastService:
    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        rate_limiter: RateLimiter,
        users: UserRepository,
    ) -> None:
        self.session = session
        self.bot = bot
        self.rate_limiter = rate_limiter
        self.users = users

    async def send(self, user_ids: Iterable[int], text: str) -> BroadcastSummary:
        sent = 0
        failed = 0
        for telegram_id in user_ids:
            allowed = await self.rate_limiter.allow_user(
                telegram_id, "broadcast", limit=20, window_seconds=60
            )
            if not allowed:
                failed += 1
                continue
            user = await self.users.get_by_telegram_id(telegram_id)
            if user is None:
                failed += 1
                continue
            try:
                await self.bot.send_message(chat_id=telegram_id, text=text)
                self.session.add(
                    MessageRecord(user_id=user.id, command="broadcast", status="sent", detail=text[:250])
                )
                sent += 1
            except Exception:
                failed += 1
                self.session.add(
                    MessageRecord(
                        user_id=user.id,
                        command="broadcast",
                        status="failed",
                        detail=text[:250],
                    )
                )
        return BroadcastSummary(sent=sent, failed=failed)
