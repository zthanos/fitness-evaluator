"""add plan_metadata to training_plans and phase/distance_target_km to training_plan_weeks

Revision ID: 022
Revises: 021
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade():
    # training_plans — store LLM-generated performance target and plan rationale
    op.add_column('training_plans', sa.Column('plan_metadata', sa.JSON(), nullable=True))

    # training_plan_weeks — phase and distance target for progression display
    op.add_column('training_plan_weeks', sa.Column('phase', sa.String(20), nullable=True))
    op.add_column('training_plan_weeks', sa.Column('distance_target_km', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('training_plan_weeks', 'distance_target_km')
    op.drop_column('training_plan_weeks', 'phase')
    op.drop_column('training_plans', 'plan_metadata')
