"""Add sync run audit table for admin control panel"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_admin_control_panel"
down_revision = "0004_telegram_profile_and_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sync_runs_source", "sync_runs", ["source"], unique=False)
    op.create_index("ix_sync_runs_status", "sync_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sync_runs_status", table_name="sync_runs")
    op.drop_index("ix_sync_runs_source", table_name="sync_runs")
    op.drop_table("sync_runs")
