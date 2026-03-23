from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TESTTOKENVALUE1234567890")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "test_bot")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET_TOKEN", "test-secret")
os.environ.setdefault("PUBLIC_BASE_URL", "https://example.com")
os.environ.setdefault("SET_WEBHOOK_ON_START", "false")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("TELEGRAM_ENABLED", "true")
