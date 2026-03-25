from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# -------------------------
# Health
# -------------------------


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service health status")


class ReadinessResponse(BaseModel):
    status: str = Field(description="Service readiness status")
    checks: dict[str, str] = Field(default_factory=dict, description="Named readiness checks")


# -------------------------
# Checkout
# -------------------------


class CheckoutSessionRequest(BaseModel):
    sku: str = Field(..., min_length=1, description="Product SKU")
    telegram_id: int = Field(..., gt=0, description="Telegram user ID")
    success_url: str = Field(..., min_length=8, description="Redirect URL on success")
    cancel_url: str = Field(..., min_length=8, description="Redirect URL on cancel")


class CheckoutSessionResponse(BaseModel):
    url: str = Field(..., description="Stripe Checkout URL")
    session_id: str = Field(..., description="Stripe session ID")


# -------------------------
# Stripe Webhooks
# -------------------------


class StripeWebhookEvent(BaseModel):
    id: str = Field(..., description="Stripe event ID")
    type: str = Field(..., description="Stripe event type")
    created: Optional[int] = Field(None, description="Unix timestamp")
    livemode: Optional[bool] = Field(None, description="Live/test mode flag")


# -------------------------
# Orders
# -------------------------


class OrderRead(BaseModel):
    id: int
    sku: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AIChatRequest(BaseModel):
    telegram_id: int = Field(..., gt=0, description="Telegram user ID")
    prompt: str = Field(..., min_length=1, description="AI prompt")


class AIChatResponse(BaseModel):
    reply: str
    tier: str
    model: str
    provider: str
    latency_ms: int
