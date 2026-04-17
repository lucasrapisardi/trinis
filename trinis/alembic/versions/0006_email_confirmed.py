# PATH: /home/lumoura/trinis_ai/trinis/alembic/versions/0006_email_confirmed.py
"""add email_confirmed to users

Revision ID: 0006_email_confirmed
Revises: 0005_cancelled_plan
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006_email_confirmed"
down_revision: Union[str, None] = "0005_cancelled_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_confirmed", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Mark existing users as confirmed so they don't get locked out
    op.execute("UPDATE users SET email_confirmed = true")


def downgrade() -> None:
    op.drop_column("users", "email_confirmed")
