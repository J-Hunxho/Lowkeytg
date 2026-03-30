"""Add retention badges and streak tracking"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_retention_badges_streaks"
down_revision = "0006_ai_usage_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_badges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("badge_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "badge_key", name="uq_user_badges_user_key"),
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"], unique=False)
    op.create_index("ix_user_badges_badge_key", "user_badges", ["badge_key"], unique=False)

    op.create_table(
        "user_streaks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("best_streak", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_seen_date", sa.Date(), nullable=False),
        sa.Column("total_logins", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_streaks_user_id", "user_streaks", ["user_id"], unique=True)
    op.create_index("ix_user_streaks_last_seen_date", "user_streaks", ["last_seen_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_streaks_last_seen_date", table_name="user_streaks")
    op.drop_index("ix_user_streaks_user_id", table_name="user_streaks")
    op.drop_table("user_streaks")

    op.drop_index("ix_user_badges_badge_key", table_name="user_badges")
    op.drop_index("ix_user_badges_user_id", table_name="user_badges")
    op.drop_table("user_badges")
