from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.web.api import app


@pytest.mark.asyncio()
async def test_healthz() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio()
async def test_telegram_webhook_secret_validation() -> None:
    settings.set_webhook_on_start = False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook/telegram",
            headers={"X-Telegram-Bot-Api-Secret-Token": "invalid"},
            content=json.dumps({"update_id": 1}),
        )
    assert response.status_code == 401
