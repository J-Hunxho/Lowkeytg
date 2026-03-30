from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.repos.users import UserRepository
from app.services.retention import RetentionService


async def _build_session() -> tuple[AsyncSession, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return session_factory(), engine


def test_retention_streak_and_leaderboard() -> None:
    async def run() -> None:
        session, engine = await _build_session()
        async with session:
            users = UserRepository(session)
            alpha = await users.create_or_update(telegram_id=1001, username="alpha")
            beta = await users.create_or_update(telegram_id=1002, username="beta")
            alpha.referral_count = 6
            beta.referral_count = 2

            retention = RetentionService(session)
            streak = await retention.touch_login(alpha)
            badges = await retention.badges_for_user(alpha)
            leaders = await retention.referral_leaderboard(limit=2)

            assert streak.current_streak >= 1
            assert any(b.badge_key == "referral_5" for b in badges)
            assert leaders[0].telegram_id == 1001
        await engine.dispose()

    asyncio.run(run())
