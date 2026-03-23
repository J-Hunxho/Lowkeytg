from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

from pydantic import AnyUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "dev"
    log_level: str = "INFO"

    telegram_enabled: bool = False
    telegram_bot_token: Optional[SecretStr] = None
    telegram_bot_username: Optional[str] = None
    telegram_webhook_secret_token: Optional[SecretStr] = None
    public_base_url: Optional[AnyUrl] = None
    railway_static_url: Optional[str] = None
    railway_public_domain: Optional[str] = None
    webhook_path: str = "/webhook/telegram"
    set_webhook_on_start: bool = False
    fail_fast_on_startup: bool = False

    stripe_enabled: bool = False
    stripe_secret_key: Optional[SecretStr] = None
    stripe_webhook_secret: Optional[SecretStr] = None

    price_id_founder_key: Optional[str] = None
    price_id_vip_month: Optional[str] = None
    price_id_vip_year: Optional[str] = None

    database_url: str = "sqlite+aiosqlite:///./data.db"
    redis_url: Optional[str] = None

    admin_user_ids: Tuple[int, ...] = ()

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admins(cls, value: str | Tuple[int, ...] | None) -> Tuple[int, ...]:
        if not value:
            return ()
        if isinstance(value, tuple):
            return value
        return tuple(int(part.strip()) for part in value.split(",") if part.strip().isdigit())

    @field_validator("railway_static_url", "railway_public_domain", mode="before")
    @classmethod
    def normalize_optional_domain(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.strip().strip("/")

    @field_validator("webhook_path", mode="before")
    @classmethod
    def normalize_webhook_path(cls, value: str | None) -> str:
        if not value:
            return "/webhook/telegram"
        normalized = "/" + "/".join(part for part in value.split("/") if part)
        return normalized or "/webhook/telegram"

    @property
    def effective_public_base_url(self) -> str:
        raw = self.public_base_url or self.railway_static_url or self.railway_public_domain
        if not raw:
            raise RuntimeError(
                "PUBLIC_BASE_URL or Railway public URL env vars are required for webhook setup"
            )

        value = str(raw).strip()
        if not value.startswith(("http://", "https://")):
            value = f"https://{value}"

        parts = urlsplit(value)
        path = "/".join(segment for segment in parts.path.split("/") if segment)
        return urlunsplit((parts.scheme, parts.netloc, f"/{path}" if path else "", "", ""))

    @property
    def mini_app_url(self) -> str:
        return self.join_public_url("/mini-app")

    @property
    def webhook_url(self) -> str:
        return self.join_public_url(self.webhook_path)

    @property
    def support_contact(self) -> str:
        return self.telegram_bot_username or "admin team"

    def join_public_url(self, path: str) -> str:
        base = self.effective_public_base_url.rstrip("/")
        normalized_path = "/" + "/".join(part for part in path.split("/") if part)
        return f"{base}{normalized_path}"

    def validate_telegram(self) -> None:
        missing: list[str] = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_webhook_secret_token:
            missing.append("TELEGRAM_WEBHOOK_SECRET_TOKEN")
        if not self.public_base_url and not self.railway_static_url and not self.railway_public_domain:
            missing.append("PUBLIC_BASE_URL/RAILWAY_STATIC_URL/RAILWAY_PUBLIC_DOMAIN")
        if missing:
            raise RuntimeError(f"Telegram configuration incomplete: {', '.join(missing)}")

    def validate_stripe(self) -> None:
        missing: list[str] = []
        if not self.stripe_secret_key:
            missing.append("STRIPE_SECRET_KEY")
        if not self.stripe_webhook_secret:
            missing.append("STRIPE_WEBHOOK_SECRET")
        if missing:
            raise RuntimeError(f"Stripe configuration incomplete: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
