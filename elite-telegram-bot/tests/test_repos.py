from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.repos.orders import OrderRepository
from app.repos.referrals import ReferralRepository
from app.repos.users import UserRepository

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


async def _build_session() -> tuple[AsyncSession, object]:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return session_factory(), engine


def test_user_referral_flow() -> None:
    async def run() -> None:
        session, engine = await _build_session()
        async with session:
            users = UserRepository(session)
            alice = await users.create_or_update(telegram_id=1, username="alice")
            bob = await users.create_or_update(telegram_id=2, username="bob")
            referrals = ReferralRepository(session)
            await users.set_referred_by(bob, alice)
            await users.increment_referral_count(alice)
            await referrals.create(referrer_id=alice.id, referred_id=bob.id)
            await session.commit()

            assert alice.referral_count == 1
            assert bob.referred_by_id == alice.id
        await engine.dispose()

    asyncio.run(run())


def test_order_repository() -> None:
    async def run() -> None:
        session, engine = await _build_session()
        async with session:
            users = UserRepository(session)
            user = await users.create_or_update(telegram_id=42, username="vip")
            orders_repo = OrderRepository(session)
            await orders_repo.create(
                user_id=user.id,
                sku="founder_key",
                price_id="price_123",
                stripe_checkout_id="cs_test",
                metadata={"foo": "bar"},
            )
            await session.commit()

            fetched = await orders_repo.get_by_checkout_id("cs_test")
            assert fetched is not None
            await orders_repo.mark_paid(fetched, payment_intent="pi_test")
            assert fetched.status == "paid"
        await engine.dispose()

    asyncio.run(run())
