from __future__ import annotations

import re

_ESCAPE_RE = re.compile(r"[_\*\[\]()~`>#+\-=|{}.!]")


def escape_markdown_v2(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    return "".join("\\" + char if _ESCAPE_RE.match(char) else char for char in text)
