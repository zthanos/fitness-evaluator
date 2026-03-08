"""Add evaluations table for performance evaluation persistence

Revision ID: 009
Revises: 008
Create Date: 2024-01-17

This migration creates the evaluations table to persist performance evaluation reports.
Evaluations include scores, strengths, improvements, tips, and exercise recommendations
for athletes over specific time periods.

Features:
- Stores evaluation metadata (athlete_id, period dates, period type)
- Stores evaluation content (scores, strengths, improvements, tips, recommendations)
- Indexes on athlete_id and created_at for efficient querying
- Check constraint for period_type values
- Timestamps for created_at and updated_at
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, Sequence[str], None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create evaluations table with indexes and constraints."""
    
    # Create evaluations table
    op.create_table(
        'evaluations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('athlete_id', sa.Integer, nullable=False),
        sa.Column('period_start', sa.Date, nullable=False),
        sa.Column('period_end', sa.Date, nullable=False),
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('overall_score', sa.Integer, nullable=False),
        sa.Column('strengths', sa.JSON, nullable=False),
        sa.Column('improvements', sa.JSON, nullable=False),
        sa.Column('tips', sa.JSON, nullable=False),
        sa.Column('recommended_exercises', sa.JSON, nullable=False),
        sa.Column('goal_alignment', sa.Text, nullable=False),
        sa.Column('confidence_score', sa.Float, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Add check constraint for period_type values
    with op.batch_alter_table('evaluations', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'check_period_type',
            "period_type IN ('weekly', 'bi-weekly', 'monthly')"
        )
    
    # Create indexes for efficient querying
    op.create_index('idx_evaluations_athlete_id', 'evaluations', ['athlete_id'])
    op.create_index('idx_evaluations_created_at', 'evaluations', ['created_at'])


def downgrade() -> None:
    """Drop evaluations table and indexes."""
    
    # Drop indexes
    op.drop_index('idx_evaluations_created_at', table_name='evaluations')
    op.drop_index('idx_evaluations_athlete_id', table_name='evaluations')
    
    # Drop table
    op.drop_table('evaluations')
