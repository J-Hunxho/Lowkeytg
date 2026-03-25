from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base
from app.models import AccessGrant, AdminSetting, Product, User
from app.services.ai.service import AIQuotaExceeded, AIService, AIServiceDisabled

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


async def _build_session() -> tuple[AsyncSession, object]:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return session_factory(), engine


def test_ai_service_resolves_paid_tier_from_grant() -> None:
    async def run() -> None:
        settings.ai_provider = "echo"
        settings.ai_enabled = True
        session, engine = await _build_session()
        async with session:
            user = User(telegram_id=1001, referral_code="ref1001")
            session.add(user)
            session.add(Product(sku="starter_month", title="Starter", access_role="starter", active=True))
            await session.flush()
            session.add(AccessGrant(user_id=user.id, sku="starter_month", active=True))
            await session.commit()

            service = AIService(session)
            snapshot = await service.usage_snapshot(user)
            assert snapshot["tier"] == "starter"
            assert snapshot["daily_limit"] >= 50
        await engine.dispose()

    asyncio.run(run())


def test_ai_service_enforces_daily_limit() -> None:
    async def run() -> None:
        settings.ai_provider = "echo"
        settings.ai_enabled = True
        session, engine = await _build_session()
        async with session:
            user = User(telegram_id=2002, referral_code="ref2002")
            session.add(user)
            session.add(
                AdminSetting(
                    key="ai_plan_rules",
                    value={"free": {"daily_limit": 1, "model": "gpt-4o-mini", "priority": "standard"}},
                )
            )
            await session.commit()

            service = AIService(session)
            first = await service.respond(user=user, prompt="hello")
            assert first["tier"] == "free"
            with_raised = False
            try:
                await service.respond(user=user, prompt="second request")
            except AIQuotaExceeded:
                with_raised = True
            assert with_raised is True
        await engine.dispose()

    asyncio.run(run())


def test_ai_service_disabled_guard() -> None:
    async def run() -> None:
        settings.ai_enabled = False
        settings.ai_provider = "echo"
        session, engine = await _build_session()
        async with session:
            user = User(telegram_id=3003, referral_code="ref3003")
            session.add(user)
            await session.commit()
            service = AIService(session)
            raised = False
            try:
                await service.usage_snapshot(user)
            except AIServiceDisabled:
                raised = True
            assert raised is True
        settings.ai_enabled = True
        await engine.dispose()

    asyncio.run(run())
