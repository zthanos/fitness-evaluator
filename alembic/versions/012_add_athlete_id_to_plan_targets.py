"""Add athlete_id to plan_targets

Revision ID: 012
Revises: 011
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('plan_targets',
        sa.Column('athlete_id', sa.Integer(),
                  sa.ForeignKey('athletes.id', ondelete='CASCADE'),
                  nullable=True)
    )
    op.create_index('ix_plan_targets_athlete_id', 'plan_targets', ['athlete_id'])


def downgrade():
    op.drop_index('ix_plan_targets_athlete_id', table_name='plan_targets')
    op.drop_column('plan_targets', 'athlete_id')
