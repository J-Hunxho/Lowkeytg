from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.bot.main import get_private_commands
from app.bootstrap import safe_sync_bot_state
from app.config import Settings, settings
from app.web.api import app


@pytest.mark.asyncio()
async def test_healthz() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio()
async def test_readyz() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["database"] == "ok"


@pytest.mark.asyncio()
async def test_mini_app_route() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/mini-app")
    assert response.status_code == 200
    assert "Lowkey Mini App" in response.text


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


@pytest.mark.asyncio()
async def test_telegram_webhook_rejects_bad_payload() -> None:
    settings.set_webhook_on_start = False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook/telegram",
            headers={"X-Telegram-Bot-Api-Secret-Token": settings.telegram_webhook_secret_token.get_secret_value()},
            content="not-json",
        )
    assert response.status_code == 400


@pytest.mark.asyncio()
async def test_safe_sync_bot_state_degrades_when_config_is_incomplete() -> None:
    cfg = Settings(telegram_enabled=True, fail_fast_on_startup=False)
    synced = await safe_sync_bot_state(bot=None, settings=cfg, command_factory=get_private_commands)
    assert synced is False


def test_webhook_url_is_normalized_for_railway_domains() -> None:
    cfg = Settings(
        telegram_enabled=True,
        telegram_bot_token="123456:ABC",
        telegram_webhook_secret_token="secret",
        public_base_url=None,
        railway_static_url="example.up.railway.app/",
        webhook_path="//telegram//",
    )
    assert cfg.effective_public_base_url == "https://example.up.railway.app"
    assert cfg.webhook_url == "https://example.up.railway.app/telegram"


def test_private_commands_expose_aliases_and_ops_commands() -> None:
    commands = {command.command for command in get_private_commands()}
    assert {"profile", "app", "ban", "unban", "pricing", "referrals", "healthcheck", "catalogsync", "status"}.issubset(commands)
