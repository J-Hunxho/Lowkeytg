"""Add AI request logging and daily usage counters"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_ai_usage_tracking"
down_revision = "0005_admin_control_panel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_request_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_request_logs_user_id", "ai_request_logs", ["user_id"], unique=False)
    op.create_index("ix_ai_request_logs_tier", "ai_request_logs", ["tier"], unique=False)
    op.create_index("ix_ai_request_logs_status", "ai_request_logs", ["status"], unique=False)
    op.create_index("ix_ai_request_logs_created_at", "ai_request_logs", ["created_at"], unique=False)

    op.create_table(
        "ai_usage_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("requests_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "usage_date", name="uq_ai_usage_daily_user_date"),
    )
    op.create_index("ix_ai_usage_daily_user_id", "ai_usage_daily", ["user_id"], unique=False)
    op.create_index("ix_ai_usage_daily_usage_date", "ai_usage_daily", ["usage_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_usage_daily_usage_date", table_name="ai_usage_daily")
    op.drop_index("ix_ai_usage_daily_user_id", table_name="ai_usage_daily")
    op.drop_table("ai_usage_daily")

    op.drop_index("ix_ai_request_logs_created_at", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_status", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_tier", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_user_id", table_name="ai_request_logs")
    op.drop_table("ai_request_logs")
