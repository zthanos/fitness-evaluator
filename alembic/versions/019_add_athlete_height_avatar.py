"""add height_cm and avatar_url to athletes

Revision ID: 019
Revises: 018
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('athletes', sa.Column('height_cm', sa.Integer(), nullable=True))
    op.add_column('athletes', sa.Column('avatar_url', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('athletes', 'avatar_url')
    op.drop_column('athletes', 'height_cm')
