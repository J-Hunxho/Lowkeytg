from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    language_code: Mapped[Optional[str]] = mapped_column(String(10))
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    referral_code: Mapped[str] = mapped_column(String(64), unique=True)
    referred_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)

    referrals: Mapped[List["Referral"]] = relationship(
        "Referral", foreign_keys="Referral.referrer_id", back_populates="referrer"
    )
    referred_users: Mapped[List["Referral"]] = relationship(
        "Referral", foreign_keys="Referral.referred_id", back_populates="referred"
    )
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user")
    purchases: Mapped[List["Purchase"]] = relationship("Purchase", back_populates="user")
    ban: Mapped[Optional["Ban"]] = relationship("Ban", back_populates="user", uselist=False)
    messages: Mapped[List["MessageRecord"]] = relationship("MessageRecord", back_populates="user")
    grants: Mapped[List["AccessGrant"]] = relationship("AccessGrant", back_populates="user")
    subscriptions: Mapped[List["StripeSubscription"]] = relationship("StripeSubscription", back_populates="user")
    telegram_profile: Mapped[Optional["TelegramProfile"]] = relationship("TelegramProfile", back_populates="user", uselist=False)


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    referrer: Mapped[User] = relationship(
        "User", foreign_keys=[referrer_id], back_populates="referrals"
    )
    referred: Mapped[User] = relationship(
        "User", foreign_keys=[referred_id], back_populates="referred_users"
    )


class TelegramProfile(Base):
    __tablename__ = "telegram_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    telegram_id: Mapped[int] = mapped_column(index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    language_code: Mapped[Optional[str]] = mapped_column(String(10))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship("User", back_populates="telegram_profile")


class StripeProduct(Base):
    __tablename__ = "stripe_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    stripe_product_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text())
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StripePrice(Base):
    __tablename__ = "stripe_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    stripe_price_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    stripe_product_id: Mapped[str] = mapped_column(String(128), index=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8))
    unit_amount: Mapped[Optional[int]] = mapped_column(Integer)
    recurring_interval: Mapped[Optional[str]] = mapped_column(String(32))
    recurring_interval_count: Mapped[Optional[int]] = mapped_column(Integer)
    type: Mapped[Optional[str]] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Product(Base):
    """Local catalog presentation layer mapped to Stripe product+price IDs."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    stripe_product_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text())
    currency: Mapped[Optional[str]] = mapped_column(String(8))
    unit_amount: Mapped[Optional[int]] = mapped_column(Integer)
    recurring_interval: Mapped[Optional[str]] = mapped_column(String(32))
    purchase_type: Mapped[Optional[str]] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_slug: Mapped[Optional[str]] = mapped_column(String(128))
    telegram_category: Mapped[Optional[str]] = mapped_column(String(128))
    delivery_type: Mapped[Optional[str]] = mapped_column(String(64))
    access_role: Mapped[Optional[str]] = mapped_column(String(64))
    channel_announcement: Mapped[Optional[str]] = mapped_column(Text())
    button_label: Mapped[Optional[str]] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sku: Mapped[str] = mapped_column(String(128))
    price_id: Mapped[str] = mapped_column(String(128))
    stripe_checkout_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_payment_intent: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON)

    user: Mapped[User] = relationship("User", back_populates="orders")
    grants: Mapped[List["AccessGrant"]] = relationship("AccessGrant", back_populates="order")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    stripe_checkout_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    stripe_payment_intent: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    stripe_product_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    amount_total: Mapped[Optional[int]] = mapped_column(Integer)
    currency: Mapped[Optional[str]] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="purchases")


class StripeSubscription(Base):
    __tablename__ = "stripe_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    stripe_product_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[Optional[User]] = relationship("User", back_populates="subscriptions")


class AccessGrant(Base):
    __tablename__ = "access_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), index=True, nullable=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="grants")
    order: Mapped[Optional[Order]] = relationship("Order", back_populates="grants")


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[Optional[str]] = mapped_column(Text())
    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIRequestLog(Base):
    __tablename__ = "ai_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tier: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    prompt: Mapped[str] = mapped_column(Text())
    response_text: Mapped[Optional[str]] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(32), index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIUsageDaily(Base):
    __tablename__ = "ai_usage_daily"
    __table_args__ = (UniqueConstraint("user_id", "usage_date", name="uq_ai_usage_daily_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    usage_date: Mapped[date] = mapped_column(Date(), index=True)
    requests_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Ban(Base):
    __tablename__ = "bans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    reason: Mapped[Optional[str]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship("User", back_populates="ban")


class MessageRecord(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    command: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    detail: Mapped[Optional[str]] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="messages")
