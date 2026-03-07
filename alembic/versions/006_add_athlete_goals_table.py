"""Add athlete_goals table for LLM-assisted goal setting

Revision ID: 006
Revises: 005
Create Date: 2024-01-16

Updates:
- Add athlete_goals table with goal types, targets, dates, and status
- Support for weight_loss, weight_gain, performance, endurance, strength, custom goal types
- Track goal status: active, completed, abandoned
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Create athlete_goals table."""
    
    op.create_table(
        'athlete_goals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('athlete_id', sa.String(36), nullable=True),  # For future multi-athlete support
        sa.Column('goal_type', sa.String(50), nullable=False),
        sa.Column('target_value', sa.Float, nullable=True),
        sa.Column('target_date', sa.Date, nullable=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Add check constraint for goal_type
    with op.batch_alter_table('athlete_goals', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'check_goal_type',
            "goal_type IN ('weight_loss', 'weight_gain', 'performance', 'endurance', 'strength', 'custom')"
        )
        
        batch_op.create_check_constraint(
            'check_status',
            "status IN ('active', 'completed', 'abandoned')"
        )
    
    # Create index on athlete_id and status for efficient queries
    op.create_index('idx_athlete_goals_athlete_id', 'athlete_goals', ['athlete_id'])
    op.create_index('idx_athlete_goals_status', 'athlete_goals', ['status'])
    op.create_index('idx_athlete_goals_created_at', 'athlete_goals', ['created_at'])


def downgrade():
    """Drop athlete_goals table."""
    
    op.drop_index('idx_athlete_goals_created_at', table_name='athlete_goals')
    op.drop_index('idx_athlete_goals_status', table_name='athlete_goals')
    op.drop_index('idx_athlete_goals_athlete_id', table_name='athlete_goals')
    op.drop_table('athlete_goals')
