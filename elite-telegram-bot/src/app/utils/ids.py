from __future__ import annotations

import secrets
import string


def generate_referral_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_request_id() -> str:
    return secrets.token_hex(8)
