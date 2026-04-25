"""add backup addon tables

Revision ID: 0010_backup_addon
Revises: 0009_job_skip_existing
Create Date: 2026-04-25 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0010_backup_addon"
down_revision: Union[str, None] = "0009_job_skip_existing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "backup_subscriptions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="basic"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("next_auto_backup_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "backup_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", sa.UUID(), sa.ForeignKey("shopify_stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("product_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minio_key", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

def downgrade() -> None:
    op.drop_table("backup_snapshots")
    op.drop_table("backup_subscriptions")
    op.execute("DROP TYPE backupstatus")
    op.execute("DROP TYPE backupplanname")
