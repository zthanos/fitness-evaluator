"""Add athlete_sport_profiles table.

Revision ID: 018
Revises: 017
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_sport_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("athlete_id", sa.Integer(),
                  sa.ForeignKey("athletes.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("sport_group", sa.String(20), nullable=False),

        # Distance & speed
        sa.Column("longest_distance_km",         sa.Float(), nullable=True),
        sa.Column("best_60min_distance_km",       sa.Float(), nullable=True),
        sa.Column("best_120min_distance_km",      sa.Float(), nullable=True),
        sa.Column("typical_endurance_speed_kmh",  sa.Float(), nullable=True),
        sa.Column("best_long_speed_kmh",          sa.Float(), nullable=True),

        # Volume
        sa.Column("weekly_volume_km",             sa.Float(), nullable=True),
        sa.Column("weekly_training_time_min",     sa.Float(), nullable=True),

        # Cadence
        sa.Column("typical_cadence_rpm",          sa.Float(), nullable=True),
        sa.Column("indoor_cadence_rpm",           sa.Float(), nullable=True),
        sa.Column("outdoor_cadence_rpm",          sa.Float(), nullable=True),
        sa.Column("climbing_cadence_rpm",         sa.Float(), nullable=True),

        # Power
        sa.Column("ftp_estimate_w",               sa.Float(), nullable=True),
        sa.Column("ftp_confidence",               sa.String(10), nullable=True),
        sa.Column("avg_power_baseline_w",         sa.Float(), nullable=True),
        sa.Column("best_weighted_power_w",        sa.Float(), nullable=True),

        # Heart rate
        sa.Column("max_hr_estimate",              sa.Integer(), nullable=True),
        sa.Column("hr_zone_model",                sa.JSON(), nullable=True),

        # Pace zones
        sa.Column("pace_zone_model",              sa.JSON(), nullable=True),

        # Coaching
        sa.Column("current_strengths",            sa.JSON(), nullable=True),
        sa.Column("current_limiters",             sa.JSON(), nullable=True),
        sa.Column("profile_confidence",           sa.Float(), nullable=True),
        sa.Column("last_updated_at",              sa.DateTime(), nullable=False),
        sa.Column("summary_text",                 sa.Text(), nullable=True),

        sa.UniqueConstraint("athlete_id", "sport_group", name="uq_athlete_sport_group"),
    )


def downgrade() -> None:
    op.drop_table("athlete_sport_profiles")
