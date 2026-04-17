"""add scrape_scope product_limit scheduled_at

Revision ID: 0002_scrape_scope_product_limit
Revises: 0001_initial
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002_scrape_scope_product_limit"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scrape_scope to vendor_configs
    op.add_column(
        "vendor_configs",
        sa.Column("scrape_scope", sa.String(20), nullable=False, server_default="pagina"),
    )

    # Add product_limit and scheduled_at to jobs
    op.add_column(
        "jobs",
        sa.Column("product_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vendor_configs", "scrape_scope")
    op.drop_column("jobs", "product_limit")
    op.drop_column("jobs", "scheduled_at")
