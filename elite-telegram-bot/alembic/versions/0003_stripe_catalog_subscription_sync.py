"""Add normalized Stripe catalog/subscription/purchase sync tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_stripe_catalog_subscription_sync"
down_revision = "0002_catalog_and_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_product_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stripe_products_stripe_product_id", "stripe_products", ["stripe_product_id"], unique=True)

    op.create_table(
        "stripe_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_price_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("stripe_product_id", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("unit_amount", sa.Integer(), nullable=True),
        sa.Column("recurring_interval", sa.String(length=32), nullable=True),
        sa.Column("recurring_interval_count", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stripe_prices_stripe_price_id", "stripe_prices", ["stripe_price_id"], unique=True)
    op.create_index("ix_stripe_prices_stripe_product_id", "stripe_prices", ["stripe_product_id"], unique=False)

    op.add_column("products", sa.Column("purchase_type", sa.String(length=32), nullable=True))
    op.add_column("products", sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("products", sa.Column("telegram_slug", sa.String(length=128), nullable=True))
    op.add_column("products", sa.Column("telegram_category", sa.String(length=128), nullable=True))
    op.add_column("products", sa.Column("delivery_type", sa.String(length=64), nullable=True))
    op.add_column("products", sa.Column("access_role", sa.String(length=64), nullable=True))
    op.add_column("products", sa.Column("channel_announcement", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("button_label", sa.String(length=128), nullable=True))

    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("stripe_checkout_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_intent", sa.String(length=255), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=128), nullable=True),
        sa.Column("stripe_product_id", sa.String(length=128), nullable=True),
        sa.Column("amount_total", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_purchases_user_id", "purchases", ["user_id"], unique=False)
    op.create_index("ix_purchases_stripe_checkout_id", "purchases", ["stripe_checkout_id"], unique=False)
    op.create_index("ix_purchases_stripe_payment_intent", "purchases", ["stripe_payment_intent"], unique=False)
    op.create_index("ix_purchases_stripe_price_id", "purchases", ["stripe_price_id"], unique=False)
    op.create_index("ix_purchases_stripe_product_id", "purchases", ["stripe_product_id"], unique=False)

    op.create_table(
        "stripe_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=128), nullable=True),
        sa.Column("stripe_product_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stripe_subscriptions_stripe_subscription_id", "stripe_subscriptions", ["stripe_subscription_id"], unique=True)
    op.create_index("ix_stripe_subscriptions_user_id", "stripe_subscriptions", ["user_id"], unique=False)
    op.create_index("ix_stripe_subscriptions_stripe_customer_id", "stripe_subscriptions", ["stripe_customer_id"], unique=False)
    op.create_index("ix_stripe_subscriptions_stripe_price_id", "stripe_subscriptions", ["stripe_price_id"], unique=False)
    op.create_index("ix_stripe_subscriptions_stripe_product_id", "stripe_subscriptions", ["stripe_product_id"], unique=False)
    op.create_index("ix_stripe_subscriptions_status", "stripe_subscriptions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stripe_subscriptions_status", table_name="stripe_subscriptions")
    op.drop_index("ix_stripe_subscriptions_stripe_product_id", table_name="stripe_subscriptions")
    op.drop_index("ix_stripe_subscriptions_stripe_price_id", table_name="stripe_subscriptions")
    op.drop_index("ix_stripe_subscriptions_stripe_customer_id", table_name="stripe_subscriptions")
    op.drop_index("ix_stripe_subscriptions_user_id", table_name="stripe_subscriptions")
    op.drop_index("ix_stripe_subscriptions_stripe_subscription_id", table_name="stripe_subscriptions")
    op.drop_table("stripe_subscriptions")

    op.drop_index("ix_purchases_stripe_product_id", table_name="purchases")
    op.drop_index("ix_purchases_stripe_price_id", table_name="purchases")
    op.drop_index("ix_purchases_stripe_payment_intent", table_name="purchases")
    op.drop_index("ix_purchases_stripe_checkout_id", table_name="purchases")
    op.drop_index("ix_purchases_user_id", table_name="purchases")
    op.drop_table("purchases")

    op.drop_column("products", "button_label")
    op.drop_column("products", "channel_announcement")
    op.drop_column("products", "access_role")
    op.drop_column("products", "delivery_type")
    op.drop_column("products", "telegram_category")
    op.drop_column("products", "telegram_slug")
    op.drop_column("products", "featured")
    op.drop_column("products", "purchase_type")

    op.drop_index("ix_stripe_prices_stripe_product_id", table_name="stripe_prices")
    op.drop_index("ix_stripe_prices_stripe_price_id", table_name="stripe_prices")
    op.drop_table("stripe_prices")

    op.drop_index("ix_stripe_products_stripe_product_id", table_name="stripe_products")
    op.drop_table("stripe_products")
