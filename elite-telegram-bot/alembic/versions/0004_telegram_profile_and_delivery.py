"""Add telegram profile model"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_telegram_profile_and_delivery"
down_revision = "0003_stripe_catalog_subscription_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=10), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_telegram_profiles_user_id", "telegram_profiles", ["user_id"], unique=True)
    op.create_index("ix_telegram_profiles_telegram_id", "telegram_profiles", ["telegram_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_telegram_profiles_telegram_id", table_name="telegram_profiles")
    op.drop_index("ix_telegram_profiles_user_id", table_name="telegram_profiles")
    op.drop_table("telegram_profiles")
