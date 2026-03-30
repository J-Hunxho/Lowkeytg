from __future__ import annotations

import asyncio

from aiogram.types import Update

from app.bot.middlewares import DBSessionMiddleware


class _Marker:
    called = False


def test_db_session_middleware_injects_session_when_missing() -> None:
    async def run() -> None:
        middleware = DBSessionMiddleware()
        marker = _Marker()

        async def handler(event, data):
            assert data.get("session") is not None
            marker.called = True
            return "ok"

        update = Update(update_id=1)
        result = await middleware(handler, update, {})
        assert result == "ok"
        assert marker.called is True

    asyncio.run(run())