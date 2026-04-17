# PATH: /home/lumoura/trinis_ai/trinis/alembic/versions/0005_cancelled_plan.py
"""add cancelled plan and cancelled_at

Revision ID: 0005_cancelled_plan
Revises: 0004_done_with_errors
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0005_cancelled_plan"
down_revision: Union[str, None] = "0004_done_with_errors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE planname ADD VALUE IF NOT EXISTS 'cancelled' AFTER 'business'")
    op.add_column(
        "tenants",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "cancelled_at")
