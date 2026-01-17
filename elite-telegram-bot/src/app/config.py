from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple

from pydantic import AnyUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─── Core Settings Behavior ──────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",                 # Local only
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",                  # Ignore unknown env vars (Railway-safe)
    )

    # ─── Runtime Environment ────────────────────────────────────────────────
    env: str = "dev"                    # dev | prod | test
    log_level: str = "INFO"

    # ─── Telegram (OPTIONAL) ────────────────────────────────────────────────
    telegram_enabled: bool = False      # 🔑 master kill-switch

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
    def parse_admins(
        cls, value: str | Tuple[int, ...] | None
    ) -> Tuple[int, ...]:
        if not value:
            return ()
        if isinstance(value, tuple):
            return value
        return tuple(
            int(part.strip())
            for part in value.split(",")
            if part.strip().isdigit()
        )

    # ─── Derived / Guarded Properties ───────────────────────────────────────
    @property
    def webhook_url(self) -> str:
        if not self.public_base_url:
            raise RuntimeError("PUBLIC_BASE_URL is required for webhooks")
        return f"{self.public_base_url}/webhook/telegram"

    def validate_telegram(self) -> None:
        """
        Call ONLY if telegram_enabled=True
        """
        if not self.telegram_enabled:
            return

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
                f"Telegram enabled but missing: {', '.join(missing)}"
            )

    def validate_stripe(self) -> None:
        """
        Call ONLY if stripe_enabled=True
        """
        if not self.stripe_enabled:
            return

        if not self.stripe_secret_key:
            raise RuntimeError("STRIPE_SECRET_KEY is required when stripe_enabled=True")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

settings: Settings = get_settings()
