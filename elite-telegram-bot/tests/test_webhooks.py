from __future__ import annotations

import asyncio
import json

from httpx import ASGITransport, AsyncClient

from app.bootstrap import safe_sync_bot_state
from app.bot.main import get_admin_commands, get_private_commands
from app.config import Settings, settings
from app.web.api import app


async def _request(method: str, path: str, **kwargs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def test_healthz() -> None:
    response = asyncio.run(_request("GET", "/healthz"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz() -> None:
    response = asyncio.run(_request("GET", "/readyz"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["database"] == "ok"
    assert response.json()["checks"]["ai_config"] in {"ok", "disabled"}


def test_mini_app_route() -> None:
    response = asyncio.run(_request("GET", "/mini-app"))
    assert response.status_code == 200
    assert "Member-Only Access Drops" in response.text


def test_telegram_webhook_secret_validation() -> None:
    settings.set_webhook_on_start = False
    response = asyncio.run(
        _request(
            "POST",
            "/webhook/telegram",
            headers={"X-Telegram-Bot-Api-Secret-Token": "invalid"},
            content=json.dumps({"update_id": 1}),
        )
    )
    assert response.status_code == 401


def test_telegram_webhook_rejects_bad_payload() -> None:
    settings.set_webhook_on_start = False
    response = asyncio.run(
        _request(
            "POST",
            "/webhook/telegram",
            headers={
                "X-Telegram-Bot-Api-Secret-Token": settings.telegram_webhook_secret_token.get_secret_value()
            },
            content="not-json",
        )
    )
    assert response.status_code == 400


def test_safe_sync_bot_state_degrades_when_config_is_incomplete() -> None:
    cfg = Settings(telegram_enabled=True, fail_fast_on_startup=False)
    synced = asyncio.run(safe_sync_bot_state(bot=None, settings=cfg, command_factory=get_private_commands))
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


def test_private_commands_are_member_focused() -> None:
    commands = {command.command for command in get_private_commands()}
    assert {
        "account",
        "app",
        "ai",
        "buy",
        "orders",
        "plans",
        "shop",
        "support",
    }.issubset(commands)
    assert "sync_products" not in commands


def test_admin_commands_contain_ops_actions() -> None:
    commands = {command.command for command in get_admin_commands()}
    assert {"sync_products", "reload_settings", "broadcast_product", "status"}.issubset(commands)


def test_admin_sync_products_requires_admin_header() -> None:
    response = asyncio.run(_request("POST", "/admin/sync-products"))
    assert response.status_code in {422, 403}


def test_account_state_endpoint() -> None:
    response = asyncio.run(_request("GET", "/api/account/state?telegram_id=999999"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["orders_count"] == 0
    assert payload["is_admin"] is False
    assert payload["streak_days"] == 0
    assert payload["badges"] == []


def test_admin_dashboard_requires_admin() -> None:
    response = asyncio.run(_request("GET", "/api/admin/dashboard", headers={"X-Admin-Telegram-Id": "999"}))
    assert response.status_code in {403, 404, 500}


def test_admin_setting_accepts_scalar_payload() -> None:
    response = asyncio.run(
        _request(
            "PUT",
            "/api/admin/settings/maintenance_mode",
            headers={"X-Admin-Telegram-Id": "999", "Content-Type": "application/json"},
            content="true",
        )
    )
    assert response.status_code in {403, 404}