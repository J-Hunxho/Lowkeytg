"""Add product catalog, stripe idempotency, access grants, and admin settings"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_catalog_and_events"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=64), nullable=False, unique=True),
        sa.Column("stripe_product_id", sa.String(length=128), nullable=True, unique=True),
        sa.Column("stripe_price_id", sa.String(length=128), nullable=True, unique=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("unit_amount", sa.Integer(), nullable=True),
        sa.Column("recurring_interval", sa.String(length=32), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stripe_events_event_id", "stripe_events", ["event_id"], unique=True)

    op.create_table(
        "access_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_access_grants_user_id", "access_grants", ["user_id"], unique=False)
    op.create_index("ix_access_grants_order_id", "access_grants", ["order_id"], unique=False)
    op.create_index("ix_access_grants_sku", "access_grants", ["sku"], unique=False)

    op.create_table(
        "admin_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_settings_key", "admin_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_admin_settings_key", table_name="admin_settings")
    op.drop_table("admin_settings")
    op.drop_index("ix_access_grants_sku", table_name="access_grants")
    op.drop_index("ix_access_grants_order_id", table_name="access_grants")
    op.drop_index("ix_access_grants_user_id", table_name="access_grants")
    op.drop_table("access_grants")
    op.drop_index("ix_stripe_events_event_id", table_name="stripe_events")
    op.drop_table("stripe_events")
    op.drop_index("ix_products_sku", table_name="products")
    op.drop_table("products")
