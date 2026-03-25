from __future__ import annotations

import httpx

from ....config import Settings
from .base import AIProviderResponse


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, *, prompt: str, model: str, user_id: int) -> AIProviderResponse:
        if not self.settings.ai_openai_api_key:
            raise RuntimeError("AI_OPENAI_API_KEY is required when AI_PROVIDER=openai")

        base_url = self.settings.ai_openai_base_url.rstrip("/")
        url = f"{base_url}/responses"
        headers = {
            "Authorization": f"Bearer {self.settings.ai_openai_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": prompt,
            "metadata": {"telegram_user_id": str(user_id)},
        }

        timeout = httpx.Timeout(float(self.settings.ai_openai_timeout_seconds))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        text = data.get("output_text") or ""
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("input_tokens") or 0)
        completion_tokens = int(usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        return AIProviderResponse(
            text=text,
            model=data.get("model") or model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
