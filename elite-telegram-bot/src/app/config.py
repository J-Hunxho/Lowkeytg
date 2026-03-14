from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple

from pydantic import AnyUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─── Core Settings Behavior ──────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",  # Local only
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars (Railway-safe)
    )

    # ─── Runtime Environment ────────────────────────────────────────────────
    env: str = "dev"  # dev | prod | test
    log_level: str = "INFO"

    # ─── Telegram (OPTIONAL) ────────────────────────────────────────────────
    telegram_enabled: bool = False  # 🔑 master kill-switch

    telegram_bot_token: Optional[SecretStr] = None
    telegram_bot_username: Optional[str] = None
    telegram_webhook_secret_token: Optional[SecretStr] = None
    public_base_url: Optional[AnyUrl] = None

    set_webhook_on_start: bool = False  # safe default

    # ─── Stripe (OPTIONAL) ──────────────────────────────────────────────────
    stripe_enabled: bool = False

    stripe_secret_key: Optional[SecretStr] = None
    stripe_webhook_secret: Optional[SecretStr] = None

    price_id_founder_key: Optional[str] = None
    price_id_vip_month: Optional[str] = None
    price_id_vip_year: Optional[str] = None

    # ─── Infrastructure ─────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data.db"
    redis_url: Optional[str] = None

    # ─── Admin / Auth ───────────────────────────────────────────────────────
    admin_user_ids: Tuple[int, ...] = ()

    # ─── Validators ─────────────────────────────────────────────────────────
    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admins(cls, value: str | Tuple[int, ...] | None) -> Tuple[int, ...]:
        if not value:
            return ()
        if isinstance(value, tuple):
            return value
        return tuple(int(part.strip()) for part in value.split(",") if part.strip().isdigit())

    # ─── Derived / Guarded Properties ───────────────────────────────────────
    class Settings(BaseSettings):
    # ─── Runtime Environment ─────────────────────────────
    env: str = "dev"
    log_level: str = "INFO"

    # ─── Telegram ───────────────────────────────────────
    telegram_enabled: bool = False
    telegram_bot_token: Optional[SecretStr] = None
    telegram_bot_username: Optional[str] = None
    telegram_webhook_secret_token: Optional[SecretStr] = None
    public_base_url: Optional[AnyUrl] = None
    set_webhook_on_start: bool = False

    # ─── Stripe ─────────────────────────────────────────
    stripe_enabled: bool = False
    stripe_secret_key: Optional[SecretStr] = None
    stripe_webhook_secret: Optional[SecretStr] = None

    price_id_founder_key: Optional[str] = None
    price_id_vip_month: Optional[str] = None
    price_id_vip_year: Optional[str] = None

    # ─── Infrastructure ─────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data.db"
    redis_url: Optional[str] = None

    # ─── Admin ──────────────────────────────────────────
    admin_user_ids: Tuple[int, ...] = ()

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admins(cls, value):
        if not value:
            return ()
        if isinstance(value, tuple):
            return value
        return tuple(int(x.strip()) for x in value.split(",") if x.strip().isdigit())

    @property
    def webhook_url(self) -> str:
        if not self.public_base_url:
            raise RuntimeError("PUBLIC_BASE_URL is required for webhooks")

        base = str(self.public_base_url).rstrip("/")
        return f"{base}/webhook/telegram"
