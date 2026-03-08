"""add_week_id_index_to_strava_activities

Revision ID: 008
Revises: 007
Create Date: 2026-03-07 12:16:03.253455

This migration creates an index on the week_id field in the strava_activities table
to support efficient querying by ISO week identifier (format: YYYY-WW).

The week_id field was added in migration 001 but the index was lost during migration 003
when tables were recreated for UUID-to-String conversion. This migration restores the index.

Note: The week_id column already exists in the database. This migration only adds the index.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, Sequence[str], None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create index on week_id column in strava_activities table."""
    
    # Create index on week_id for query performance
    # The week_id column already exists from migration 001, but the index was lost in migration 003
    op.create_index('ix_strava_activities_week_id', 'strava_activities', ['week_id'])


def downgrade() -> None:
    """Remove week_id index from strava_activities table."""
    
    # Drop index
    op.drop_index('ix_strava_activities_week_id', table_name='strava_activities')
