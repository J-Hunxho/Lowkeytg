from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class AIProviderResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AIProvider(Protocol):
    name: str

    async def generate(self, *, prompt: str, model: str, user_id: int) -> AIProviderResponse: ...
