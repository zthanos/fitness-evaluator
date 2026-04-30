"""add route_profile_id to training_plans

Revision ID: 021
Revises: 020
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'training_plans',
        sa.Column(
            'route_profile_id',
            sa.Integer(),
            sa.ForeignKey('route_profiles.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('idx_training_plans_route_profile_id', 'training_plans', ['route_profile_id'])


def downgrade():
    op.drop_index('idx_training_plans_route_profile_id', table_name='training_plans')
    op.drop_column('training_plans', 'route_profile_id')
