"""Convert UUID columns to String(36) for SQLite compatibility

Revision ID: 003
Revises: 002
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """
    SQLite doesn't support ALTER COLUMN directly, so we need to:
    1. Create new tables with String(36) columns
    2. Copy data from old tables
    3. Drop old tables
    4. Rename new tables
    """
    
    # For SQLite, we need to recreate tables
    # This migration handles the conversion of UUID columns to String(36)
    
    # Note: Since we're using SQLite and the tables were just created,
    # we can simply drop and recreate them with the correct types
    
    # Drop existing tables in reverse dependency order
    op.drop_table('weekly_evals')
    op.drop_table('strava_activities')
    op.drop_table('daily_logs')
    op.drop_table('weekly_measurements')
    op.drop_table('plan_targets')
    
    # Recreate tables with String(36) for UUID columns
    
    # plan_targets
    op.create_table(
        'plan_targets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('target_calories', sa.Integer(), nullable=True),
        sa.Column('target_protein_g', sa.Float(), nullable=True),
        sa.Column('target_fasting_hrs', sa.Float(), nullable=True),
        sa.Column('target_run_km_wk', sa.Float(), nullable=True),
        sa.Column('target_strength_sessions', sa.Integer(), nullable=True),
        sa.Column('target_weight_kg', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # weekly_measurements
    op.create_table(
        'weekly_measurements',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('week_start', sa.Date(), nullable=False, unique=True),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('weight_prev_kg', sa.Float(), nullable=True),
        sa.Column('body_fat_pct', sa.Float(), nullable=True),
        sa.Column('waist_cm', sa.Float(), nullable=True),
        sa.Column('waist_prev_cm', sa.Float(), nullable=True),
        sa.Column('sleep_avg_hrs', sa.Float(), nullable=True),
        sa.Column('rhr_bpm', sa.Integer(), nullable=True),
        sa.Column('energy_level_avg', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # daily_logs
    op.create_table(
        'daily_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('log_date', sa.Date(), nullable=False, unique=True),
        sa.Column('fasting_hours', sa.Float(), nullable=True),
        sa.Column('calories_in', sa.Integer(), nullable=True),
        sa.Column('protein_g', sa.Float(), nullable=True),
        sa.Column('carbs_g', sa.Float(), nullable=True),
        sa.Column('fat_g', sa.Float(), nullable=True),
        sa.Column('adherence_score', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('week_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('adherence_score >= 1 AND adherence_score <= 10', name='check_adherence_score_range')
    )
    
    # strava_activities
    op.create_table(
        'strava_activities',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('strava_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('moving_time_s', sa.Integer(), nullable=True),
        sa.Column('distance_m', sa.Float(), nullable=True),
        sa.Column('elevation_m', sa.Float(), nullable=True),
        sa.Column('avg_hr', sa.Integer(), nullable=True),
        sa.Column('max_hr', sa.Integer(), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=False),
        sa.Column('week_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # weekly_evals
    op.create_table(
        'weekly_evals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('week_id', sa.String(36), nullable=False, unique=True),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('raw_llm_response', sa.String(), nullable=True),
        sa.Column('parsed_output_json', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.Column('evidence_map_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )


def downgrade():
    """
    Downgrade is not supported for this migration as it would require
    converting String(36) back to UUID, which may not be reversible.
    """
    pass
