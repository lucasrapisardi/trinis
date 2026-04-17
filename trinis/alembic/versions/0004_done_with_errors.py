# PATH: /home/lumoura/trinis_ai/trinis/alembic/versions/0004_done_with_errors.py
"""add done_with_errors status and error_summary

Revision ID: 0004_done_with_errors
Revises: 0003_add_starter_plan
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0004_done_with_errors"
down_revision: Union[str, None] = "0003_add_starter_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new status to jobstatus enum
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'done_with_errors' AFTER 'done'")

    # Add error_summary column to jobs
    op.add_column(
        "jobs",
        sa.Column("error_summary", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "error_summary")
    # Note: PostgreSQL does not support removing enum values
