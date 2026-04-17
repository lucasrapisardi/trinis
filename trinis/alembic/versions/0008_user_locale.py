# PATH: /home/lumoura/trinis_ai/trinis/alembic/versions/0008_user_locale.py
"""add locale to users

Revision ID: 0008_user_locale
Revises: 0007_audit_logs
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0008_user_locale"
down_revision: Union[str, None] = "0007_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("locale", sa.String(5), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    op.drop_column("users", "locale")
