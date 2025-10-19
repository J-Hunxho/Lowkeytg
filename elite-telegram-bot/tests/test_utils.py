from __future__ import annotations

from app.utils.ids import generate_referral_code
from app.utils.markdown import escape_markdown_v2


def test_generate_referral_code_unique_length() -> None:
    code = generate_referral_code(12)
    assert len(code) == 12
    assert code.isalnum()


def test_escape_markdown_v2() -> None:
    text = "Hello_*[]()"
    escaped = escape_markdown_v2(text)
    assert escaped == "Hello\_\*\[\]\(\)"
