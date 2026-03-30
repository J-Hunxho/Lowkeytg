from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...logging import logger
from ...models import (
    AccessGrant,
    AdminSetting,
    AIRequestLog,
    AIUsageDaily,
    Product,
    StripeSubscription,
    User,
)
from .providers.base import AIProvider, AIProviderResponse
from .providers.echo import EchoAIProvider
from .providers.openai import OpenAIProvider


@dataclass
class AIPlanRule:
    daily_limit: int
    model: str
    priority: str


DEFAULT_PLAN_RULES: dict[str, AIPlanRule] = {
    "free": AIPlanRule(daily_limit=5, model="gpt-4o-mini", priority="standard"),
    "starter": AIPlanRule(daily_limit=50, model="gpt-4o-mini", priority="standard"),
    "pro": AIPlanRule(daily_limit=250, model="gpt-4.1-mini", priority="high"),
    "enterprise": AIPlanRule(daily_limit=2000, model="gpt-4.1", priority="priority"),
}
TIER_ORDER = {"free": 0, "starter": 1, "pro": 2, "enterprise": 3}


class AIQuotaExceeded(Exception):
    pass


class AIServiceDisabled(Exception):
    pass


class AIService:
    def __init__(self, session: AsyncSession, provider: AIProvider | None = None) -> None:
        self.session = session
        self.settings = get_settings()
        self.provider = provider or self._provider_from_settings(self.settings.ai_provider)
        self.default_model = self.settings.ai_default_model

    def _provider_from_settings(self, provider_name: str) -> AIProvider:
        if provider_name == "openai":
            return OpenAIProvider(self.settings)
        if provider_name == "echo":
            return EchoAIProvider()
        logger.warning("ai.unknown_provider_fallback", provider=provider_name)
        return EchoAIProvider()

    async def _get_setting(self, key: str) -> Any:
        row = await self.session.scalar(select(AdminSetting).where(AdminSetting.key == key))
        return row.value if row else None

    async def _plan_rules(self) -> dict[str, AIPlanRule]:
        raw = await self._get_setting("ai_plan_rules")
        rules = dict(DEFAULT_PLAN_RULES)
        if not isinstance(raw, dict):
            return rules
        for tier, cfg in raw.items():
            if tier not in rules or not isinstance(cfg, dict):
                continue
            limit = int(cfg.get("daily_limit", rules[tier].daily_limit))
            model = str(cfg.get("model", rules[tier].model))
            priority = str(cfg.get("priority", rules[tier].priority))
            rules[tier] = AIPlanRule(daily_limit=max(0, limit), model=model, priority=priority)
        return rules

    async def _tier_config(self) -> dict[str, dict[str, list[str]]]:
        raw = await self._get_setting("ai_tier_entitlements")
        defaults = {
            "starter": {"skus": ["starter", "vip_month"], "roles": ["starter"]},
            "pro": {"skus": ["pro", "vip_year"], "roles": ["pro", "vip"]},
            "enterprise": {"skus": ["enterprise", "founder"], "roles": ["enterprise"]},
        }
        if isinstance(raw, dict):
            for tier, cfg in raw.items():
                if not isinstance(cfg, dict):
                    continue
                defaults[tier] = {
                    "skus": [str(v).lower() for v in cfg.get("skus", defaults.get(tier, {}).get("skus", []))],
                    "roles": [str(v).lower() for v in cfg.get("roles", defaults.get(tier, {}).get("roles", []))],
                }
        return defaults

    async def _active_entitlement_products(self, user: User) -> list[Product]:
        grants = list(
            (
                await self.session.execute(
                    select(AccessGrant).where(AccessGrant.user_id == user.id, AccessGrant.active.is_(True))
                )
            ).scalars()
        )
        sub_rows = list(
            (
                await self.session.execute(
                    select(StripeSubscription).where(
                        StripeSubscription.user_id == user.id,
                        StripeSubscription.status.in_(["active", "trialing", "past_due"]),
                    )
                )
            ).scalars()
        )

        skus = {g.sku for g in grants if g.sku}
        price_ids = {s.stripe_price_id for s in sub_rows if s.stripe_price_id}
        product_ids = {s.stripe_product_id for s in sub_rows if s.stripe_product_id}

        products: list[Product] = []
        if skus:
            products.extend(list((await self.session.execute(select(Product).where(Product.sku.in_(skus)))).scalars()))
        if price_ids:
            products.extend(
                list((await self.session.execute(select(Product).where(Product.stripe_price_id.in_(price_ids)))).scalars())
            )
        if product_ids:
            products.extend(
                list(
                    (await self.session.execute(select(Product).where(Product.stripe_product_id.in_(product_ids)))).scalars()
                )
            )

        by_sku = {p.sku: p for p in products if p.sku}
        return list(by_sku.values())

    async def resolve_tier(self, user: User) -> str:
        if user.is_admin:
            return "enterprise"

        tier_config = await self._tier_config()
        products = await self._active_entitlement_products(user)
        resolved = "free"
        for product in products:
            sku = (product.sku or "").lower()
            role = (product.access_role or "").lower()
            for tier, cfg in tier_config.items():
                sku_match = any(token in sku for token in cfg.get("skus", []))
                role_match = role in cfg.get("roles", [])
                if sku_match or role_match:
                    if TIER_ORDER.get(tier, 0) > TIER_ORDER.get(resolved, 0):
                        resolved = tier
        return resolved

    async def usage_snapshot(self, user: User) -> dict[str, Any]:
        if not self.settings.ai_enabled:
            raise AIServiceDisabled("AI service is disabled")
        rules = await self._plan_rules()
        tier = await self.resolve_tier(user)
        rule = rules.get(tier, rules["free"])
        today = date.today()
        counter = await self.session.scalar(
            select(AIUsageDaily).where(AIUsageDaily.user_id == user.id, AIUsageDaily.usage_date == today)
        )
        used = int(counter.requests_count if counter else 0)
        remaining = max(0, rule.daily_limit - used)
        return {
            "tier": tier,
            "daily_limit": rule.daily_limit,
            "used_today": used,
            "remaining_today": remaining,
            "model": rule.model or self.default_model,
            "priority": rule.priority,
            "provider": self.provider.name,
        }

    async def _increment_usage(self, user: User, tokens: int) -> AIUsageDaily:
        today = date.today()
        counter = await self.session.scalar(
            select(AIUsageDaily).where(AIUsageDaily.user_id == user.id, AIUsageDaily.usage_date == today)
        )
        if counter is None:
            counter = AIUsageDaily(user_id=user.id, usage_date=today, requests_count=0, tokens_count=0)
            self.session.add(counter)
        counter.requests_count += 1
        counter.tokens_count += max(0, tokens)
        return counter

    async def _log_request(
        self,
        *,
        user: User,
        tier: str,
        model: str,
        prompt: str,
        status: str,
        response: AIProviderResponse | None = None,
        latency_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        self.session.add(
            AIRequestLog(
                user_id=user.id,
                tier=tier,
                provider=self.provider.name,
                model=model,
                prompt=prompt,
                response_text=response.text if response else None,
                status=status,
                prompt_tokens=response.prompt_tokens if response else 0,
                completion_tokens=response.completion_tokens if response else 0,
                total_tokens=response.total_tokens if response else 0,
                latency_ms=latency_ms,
                error_message=error_message,
            )
        )

    async def respond(self, *, user: User, prompt: str) -> dict[str, Any]:
        if not self.settings.ai_enabled:
            raise AIServiceDisabled("AI service is disabled")
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("Prompt is required")

        snapshot = await self.usage_snapshot(user)
        if snapshot["remaining_today"] <= 0:
            await self._log_request(
                user=user,
                tier=snapshot["tier"],
                model=snapshot["model"],
                prompt=prompt,
                status="quota_exceeded",
                error_message="daily_limit_exceeded",
            )
            raise AIQuotaExceeded("Daily AI quota exceeded for current plan")

        start = perf_counter()
        try:
            provider_response = await self.provider.generate(
                prompt=prompt,
                model=snapshot["model"],
                user_id=user.telegram_id,
            )
            latency_ms = int((perf_counter() - start) * 1000)
            await self._increment_usage(user, provider_response.total_tokens)
            await self._log_request(
                user=user,
                tier=snapshot["tier"],
                model=provider_response.model,
                prompt=prompt,
                status="ok",
                response=provider_response,
                latency_ms=latency_ms,
            )
            return {
                "reply": provider_response.text,
                "tier": snapshot["tier"],
                "model": provider_response.model,
                "provider": self.provider.name,
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            latency_ms = int((perf_counter() - start) * 1000)
            await self._log_request(
                user=user,
                tier=snapshot["tier"],
                model=snapshot["model"],
                prompt=prompt,
                status="failed",
                error_message=str(exc),
                latency_ms=latency_ms,
            )
            raise