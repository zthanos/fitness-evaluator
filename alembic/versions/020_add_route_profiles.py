"""add route_profiles table

Revision ID: 020
Revises: 019
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'route_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('athlete_id', sa.Integer(), sa.ForeignKey('athletes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=True),
        sa.Column('sport', sa.String(20), nullable=False),
        sa.Column('gpx_hash', sa.String(64), nullable=True, index=True),
        sa.Column('distance_km', sa.Float(), nullable=True),
        sa.Column('total_elevation_gain_m', sa.Float(), nullable=True),
        sa.Column('total_elevation_loss_m', sa.Float(), nullable=True),
        sa.Column('max_elevation_m', sa.Float(), nullable=True),
        sa.Column('min_elevation_m', sa.Float(), nullable=True),
        sa.Column('max_gradient_pct', sa.Float(), nullable=True),
        sa.Column('avg_climb_gradient_pct', sa.Float(), nullable=True),
        sa.Column('difficulty_score', sa.Float(), nullable=True),
        sa.Column('route_difficulty', sa.String(20), nullable=True),
        sa.Column('climb_segments', sa.JSON(), nullable=True),
        sa.Column('descent_segments', sa.JSON(), nullable=True),
        sa.Column('flat_segments', sa.JSON(), nullable=True),
        sa.Column('critical_sections', sa.JSON(), nullable=True),
        sa.Column('elevation_profile', sa.JSON(), nullable=True),
        sa.Column('analysis_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('route_profiles')
