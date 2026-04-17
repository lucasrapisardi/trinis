"""add starter plan

Revision ID: 0003_add_starter_plan
Revises: 0002_scrape_scope_product_limit
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003_add_starter_plan"
down_revision: Union[str, None] = "0002_scrape_scope_product_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE planname ADD VALUE IF NOT EXISTS 'starter' AFTER 'free'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly
    # To downgrade, recreate the type without 'starter'
    op.execute("""
        ALTER TABLE tenants ALTER COLUMN plan TYPE VARCHAR(20);
        DROP TYPE planname;
        CREATE TYPE planname AS ENUM ('free', 'pro', 'business');
        ALTER TABLE tenants ALTER COLUMN plan TYPE planname USING plan::planname;
    """)
