from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple

from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env",), env_file_encoding="utf-8", case_sensitive=False)

    telegram_bot_token: SecretStr
    telegram_bot_username: str
    telegram_webhook_secret_token: SecretStr
    public_base_url: AnyHttpUrl

    stripe_secret_key: Optional[SecretStr] = None
    stripe_webhook_secret: Optional[SecretStr] = None
    price_id_founder_key: Optional[str] = None
    price_id_vip_month: Optional[str] = None
    price_id_vip_year: Optional[str] = None

    database_url: str = "sqlite+aiosqlite:///./data.db"
    redis_url: Optional[str] = None

    admin_user_ids: Tuple[int, ...] = ()

    set_webhook_on_start: bool = True
    log_level: str = "INFO"
    env: str = "dev"

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def _parse_admins(cls, value: str | Tuple[int, ...] | None) -> Tuple[int, ...]:
        if value in (None, ""):
            return ()
        if isinstance(value, tuple):
            return value
        return tuple(int(part.strip()) for part in value.split(",") if part.strip())

    @property
    def webhook_url(self) -> str:
        return f"{self.public_base_url}/webhook/telegram"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
