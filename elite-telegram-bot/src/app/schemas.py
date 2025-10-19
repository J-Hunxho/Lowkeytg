from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"


class CheckoutSessionRequest(BaseModel):
    sku: str
    telegram_id: int
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    url: str
    session_id: str


class StripeWebhookEvent(BaseModel):
    id: str
    type: str


class OrderRead(BaseModel):
    id: int
    sku: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True
