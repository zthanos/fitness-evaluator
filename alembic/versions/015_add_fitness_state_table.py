"""Add athlete_fitness_states table

Revision ID: 015
Revises: 014
Create Date: 2026-04-26

Persisted structured state produced by FitnessStateBuilder.
One row per athlete, upserted on every analyze_recent_workout call.
"""
from alembic import op
import sqlalchemy as sa

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'athlete_fitness_states',
        sa.Column('athlete_id',             sa.Integer(),  sa.ForeignKey('athletes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('comfort_cadence_indoor', sa.Float(),    nullable=True),
        sa.Column('comfort_cadence_outdoor',sa.Float(),    nullable=True),
        sa.Column('climbing_cadence',       sa.Float(),    nullable=True),
        sa.Column('current_limiter',        sa.String(100),nullable=True),
        sa.Column('limiter_confidence',     sa.Float(),    nullable=True),
        sa.Column('fatigue_level',          sa.String(20), nullable=True),
        sa.Column('weekly_consistency',     sa.Float(),    nullable=True),
        sa.Column('acwr_ratio',             sa.Float(),    nullable=True),
        sa.Column('hr_response_trend',      sa.String(20), nullable=True),
        sa.Column('rhr_trend',              sa.String(20), nullable=True),
        sa.Column('state_confidence',       sa.Float(),    nullable=True),
        sa.Column('last_updated_at',        sa.DateTime(), nullable=False),
        sa.Column('summary_text',           sa.Text(),     nullable=True),
        sa.Column('created_at',             sa.DateTime(), nullable=True),
        sa.Column('updated_at',             sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('athlete_fitness_states')
