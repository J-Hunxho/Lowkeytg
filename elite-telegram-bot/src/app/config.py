from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple

from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ─── Core Telegram / Webhook (OPTIONAL AT BOOT) ────────────────────────────
    telegram_bot_token: Optional[SecretStr] = None
    telegram_bot_username: Optional[str] = None
    telegram_webhook_secret_token: Optional[SecretStr] = None
    public_base_url: Optional[AnyHttpUrl] = None

    # ─── Stripe (Optional) ────────────────────────────────────────────────────
    stripe_secret_key: Optional[SecretStr] = None
    stripe_webhook_secret: Optional[SecretStr] = None
    price_id_founder_key: Optional[str] = None
    price_id_vip_month: Optional[str] = None
    price_id_vip_year: Optional[str] = None

    # ─── Infrastructure ──────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data.db"
    redis_url: Optional[str] = None

    # ─── Admin / Runtime ─────────────────────────────────────────────────────
    admin_user_ids: Tuple[int, ...] = ()
    set_webhook_on_start: bool = False
    log_level: str = "INFO"
    env: str = "dev"

    # ─── Validators ──────────────────────────────────────────────────────────
    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def _parse_admins(
        cls, value: str | Tuple[int, ...] | None
    ) -> Tuple[int, ...]:
        if value in (None, ""):
            return ()
        if isinstance(value, tuple):
            return value
        return tuple(int(part.strip()) for part in value.split(",") if part.strip())

    # ─── Guards / Derived Values ──────────────────────────────────────────────
    @property
    def webhook_url(self) -> str:
        if not self.public_base_url:
            raise RuntimeError("PUBLIC_BASE_URL is not set")
        return f"{self.public_base_url}/webhook/telegram"

    def require_telegram(self) -> None:
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_bot_username:
            missing.append("TELEGRAM_BOT_USERNAME")
        if not self.telegram_webhook_secret_token:
            missing.append("TELEGRAM_WEBHOOK_SECRET_TOKEN")
        if not self.public_base_url:
            missing.append("PUBLIC_BASE_URL")

        if missing:
            raise RuntimeError(
                f"Telegram is not configured. Missing: {', '.join(missing)}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
