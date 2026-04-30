"""add plan_type to training_plans

Revision ID: 023
Revises: 022
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'training_plans',
        sa.Column('plan_type', sa.String(20), nullable=False, server_default='primary'),
    )


def downgrade():
    op.drop_column('training_plans', 'plan_type')
