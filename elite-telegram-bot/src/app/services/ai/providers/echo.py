from __future__ import annotations

from .base import AIProviderResponse


class EchoAIProvider:
    name = "echo"

    async def generate(self, *, prompt: str, model: str, user_id: int) -> AIProviderResponse:
        text = (
            "AI provider placeholder response. "
            f"Model={model}; User={user_id}; Prompt='{prompt[:500]}'"
        )
        prompt_tokens = max(1, len(prompt.split()))
        completion_tokens = max(8, len(text.split()))
        return AIProviderResponse(
            text=text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
