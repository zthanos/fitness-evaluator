"""Add calories column to strava_activities

Revision ID: 004
Revises: 003
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Add calories column to strava_activities table"""
    op.add_column('strava_activities', sa.Column('calories', sa.Float(), nullable=True))


def downgrade():
    """Remove calories column from strava_activities table"""
    op.drop_column('strava_activities', 'calories')
