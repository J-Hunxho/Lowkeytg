from __future__ import annotations

import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "test_bot")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET_TOKEN", "test-secret")
os.environ.setdefault("PUBLIC_BASE_URL", "https://example.com")
os.environ.setdefault("SET_WEBHOOK_ON_START", "false")
os.environ.setdefault("ENV", "test")
