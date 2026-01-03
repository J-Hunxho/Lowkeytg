from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, Sequence

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MessageRecord
from ..repos.users import UserRepository
from ..services.rate_limit import RateLimiter


@dataclass(slots=True)
class BroadcastSummary:
    sent: int
    failed: int
    skipped: int


class BroadcastService:
    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        rate_limiter: RateLimiter,
        users: UserRepository,
        *,
        concurrency: int = 10,
    ) -> None:
        self.session = session
        self.bot = bot
        self.rate_limiter = rate_limiter
        self.users = users
        self._semaphore = asyncio.Semaphore(concurrency)

    async def send(
        self,
        user_ids: Iterable[int],
        text: str,
    ) -> BroadcastSummary:
        sent = 0
        failed = 0
        skipped = 0
        records: list[MessageRecord] = []

        async def _send_one(telegram_id: int) -> None:
            nonlocal sent, failed, skipped

            async with self._semaphore:
                allowed = await self.rate_limiter.allow_user(
                    telegram_id,
                    "broadcast",
                    limit=20,
                    window_seconds=60,
                )
                if not allowed:
                    skipped += 1
                    return

                user = await self.users.get_by_telegram_id(telegram_id)
                if user is None:
                    skipped += 1
                    return

                try:
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=text,
                        disable_web_page_preview=True,
                    )
                    records.append(
                        MessageRecord(
                            user_id=user.id,
                            command="broadcast",
                            status="sent",
                            detail=text[:250],
                        )
                    )
                    sent += 1
                except Exception as exc:
                    records.append(
                        MessageRecord(
                            user_id=user.id,
                            command="broadcast",
                            status="failed",
                            detail=str(exc)[:250],
                        )
                    )
                    failed += 1

        tasks = [asyncio.create_task(_send_one(uid)) for uid in user_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        if records:
            self.session.add_all(records)

        return BroadcastSummary(
            sent=sent,
            failed=failed,
            skipped=skipped,
        )
