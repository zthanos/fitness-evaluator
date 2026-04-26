"""Add cadence, power, trainer, sport_type metrics to strava_activities

Revision ID: 014
Revises: 013
Create Date: 2026-04-26

Extracts v1 enrichment fields from raw_json so WorkoutAnalyzer can
query them directly without parsing JSON per row.
"""
from alembic import op
import sqlalchemy as sa

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('strava_activities', sa.Column('avg_cadence',       sa.Float(),   nullable=True))
    op.add_column('strava_activities', sa.Column('max_cadence',       sa.Float(),   nullable=True))
    op.add_column('strava_activities', sa.Column('avg_watts',         sa.Float(),   nullable=True))
    op.add_column('strava_activities', sa.Column('max_watts',         sa.Float(),   nullable=True))
    op.add_column('strava_activities', sa.Column('weighted_avg_watts',sa.Float(),   nullable=True))
    op.add_column('strava_activities', sa.Column('kilojoules',        sa.Float(),   nullable=True))
    op.add_column('strava_activities', sa.Column('suffer_score',      sa.Integer(), nullable=True))
    op.add_column('strava_activities', sa.Column('trainer',           sa.Integer(), nullable=True))
    op.add_column('strava_activities', sa.Column('sport_type',        sa.String(50),nullable=True))


def downgrade():
    for col in ('sport_type', 'trainer', 'suffer_score', 'kilojoules',
                'weighted_avg_watts', 'max_watts', 'avg_watts',
                'max_cadence', 'avg_cadence'):
        op.drop_column('strava_activities', col)
