"""user_tour_completed autogenerate

Revision ID: 6083bd7ecbe9
Revises: d9b428ccd018
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa

revision = '6083bd7ecbe9'
down_revision = 'd9b428ccd018'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('tour_completed', sa.Boolean(), nullable=False, server_default='false'))

def downgrade() -> None:
    op.drop_column('users', 'tour_completed')
