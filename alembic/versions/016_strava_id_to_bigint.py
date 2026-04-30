"""Change strava_id column to BIGINT

Revision ID: 016
Revises: 015
Create Date: 2026-04-26

Strava activity IDs exceed PostgreSQL INTEGER range (max ~2.1B).
Recent IDs such as 18254419171 require BIGINT.
"""
from alembic import op
import sqlalchemy as sa

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'strava_activities',
        'strava_id',
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        'strava_activities',
        'strava_id',
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
        existing_nullable=False,
    )
