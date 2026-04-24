"""add skip_existing to jobs

Revision ID: 0009_job_skip_existing
Revises: 0008_user_locale
Create Date: 2026-04-24 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0009_job_skip_existing"
down_revision: Union[str, None] = "0008_user_locale"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("jobs", sa.Column("skip_existing", sa.Boolean(), nullable=False, server_default="false"))

def downgrade() -> None:
    op.drop_column("jobs", "skip_existing")
