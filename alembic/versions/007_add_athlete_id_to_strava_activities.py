"""Add athlete_id to strava_activities table

Revision ID: 007
Revises: 006
Create Date: 2024-01-20

This migration adds the athlete_id foreign key column to the strava_activities table
to support multi-athlete functionality in the V2 platform.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add athlete_id column to strava_activities table."""
    
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('strava_activities', schema=None) as batch_op:
        # Add athlete_id column (nullable initially to allow existing data)
        batch_op.add_column(
            sa.Column('athlete_id', sa.Integer(), nullable=True)
        )
        
        # Add foreign key constraint
        batch_op.create_foreign_key(
            'fk_strava_activities_athlete_id',
            'athletes',
            ['athlete_id'],
            ['id'],
            ondelete='CASCADE'
        )
        
        # Add index for performance
        batch_op.create_index('ix_strava_activities_athlete_id', ['athlete_id'])
    
    # Set default athlete_id to 1 for existing records
    # This assumes athlete with id=1 exists from migration 002
    op.execute("UPDATE strava_activities SET athlete_id = 1 WHERE athlete_id IS NULL")


def downgrade() -> None:
    """Remove athlete_id column from strava_activities table."""
    
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('strava_activities', schema=None) as batch_op:
        # Drop index
        batch_op.drop_index('ix_strava_activities_athlete_id')
        
        # Drop foreign key constraint
        batch_op.drop_constraint('fk_strava_activities_athlete_id', type_='foreignkey')
        
        # Drop column
        batch_op.drop_column('athlete_id')
