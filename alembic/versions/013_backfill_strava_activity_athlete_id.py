"""Backfill athlete_id on strava_activities that were synced without auth

Revision ID: 013
Revises: 012
Create Date: 2026-04-26

Assigns all strava_activities with athlete_id IS NULL to the athlete
who owns the Strava token, since the app was previously single-user.
"""
from alembic import op

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE strava_activities
        SET athlete_id = (
            SELECT athlete_id FROM strava_tokens
            ORDER BY athlete_id ASC
            LIMIT 1
        )
        WHERE athlete_id IS NULL
          AND EXISTS (SELECT 1 FROM strava_tokens)
    """)


def downgrade():
    pass
