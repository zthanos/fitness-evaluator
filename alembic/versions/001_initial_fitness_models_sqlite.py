# alembic/versions/001_initial_fitness_models_sqlite.py
"""
Initial migration for fitness tracking models (SQLite compatible).
Creates tables for daily logs, weekly measurements, Strava activities,
plan targets, and weekly evaluations.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all fitness tracking tables."""
    
    # Daily logs table
    op.create_table(
        'daily_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('log_date', sa.Date(), nullable=False, unique=True),
        sa.Column('fasting_hours', sa.Float(), nullable=True),
        sa.Column('calories_in', sa.Integer(), nullable=True),
        sa.Column('protein_g', sa.Float(), nullable=True),
        sa.Column('carbs_g', sa.Float(), nullable=True),
        sa.Column('fat_g', sa.Float(), nullable=True),
        sa.Column('adherence_score', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('week_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('adherence_score >= 1 AND adherence_score <= 10', name='check_adherence_score_range')
    )
    op.create_index('ix_daily_logs_log_date', 'daily_logs', ['log_date'])
    op.create_index('ix_daily_logs_week_id', 'daily_logs', ['week_id'])
    
    # Weekly measurements table
    op.create_table(
        'weekly_measurements',
        sa.Column('id', sa.String(length=36), nullable=False),
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
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_weekly_measurements_week_start', 'weekly_measurements', ['week_start'])
    
    # Strava activities table
    op.create_table(
        'strava_activities',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('strava_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('activity_type', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('moving_time_s', sa.Integer(), nullable=True),
        sa.Column('distance_m', sa.Float(), nullable=True),
        sa.Column('elevation_m', sa.Float(), nullable=True),
        sa.Column('avg_hr', sa.Integer(), nullable=True),
        sa.Column('max_hr', sa.Integer(), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=False),
        sa.Column('week_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strava_id', name='uq_strava_id')
    )
    op.create_index('ix_strava_activities_strava_id', 'strava_activities', ['strava_id'], unique=True)
    op.create_index('ix_strava_activities_week_id', 'strava_activities', ['week_id'])
    op.create_index('ix_strava_activities_start_date', 'strava_activities', ['start_date'])
    
    # Plan targets table
    op.create_table(
        'plan_targets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('target_calories', sa.Integer(), nullable=True),
        sa.Column('target_protein_g', sa.Float(), nullable=True),
        sa.Column('target_fasting_hrs', sa.Float(), nullable=True),
        sa.Column('target_run_km_wk', sa.Float(), nullable=True),
        sa.Column('target_strength_sessions', sa.Integer(), nullable=True),
        sa.Column('target_weight_kg', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_plan_targets_effective_from', 'plan_targets', ['effective_from'])
    
    # Weekly evaluations table
    op.create_table(
        'weekly_evals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('week_id', sa.String(length=36), nullable=False),
        sa.Column('input_hash', sa.String(length=64), nullable=False),
        sa.Column('llm_model', sa.String(length=100), nullable=True),
        sa.Column('raw_llm_response', sa.String(), nullable=True),
        sa.Column('parsed_output_json', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.Column('evidence_map_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('week_id', name='uq_weekly_evals_week_id')
    )
    op.create_index('ix_weekly_evals_week_id', 'weekly_evals', ['week_id'])
    op.create_index('ix_weekly_evals_input_hash', 'weekly_evals', ['input_hash'])


def downgrade() -> None:
    """Drop all fitness tracking tables in reverse order."""
    
    # Drop tables with foreign key dependencies first
    op.drop_index('ix_weekly_evals_input_hash', table_name='weekly_evals')
    op.drop_index('ix_weekly_evals_week_id', table_name='weekly_evals')
    op.drop_table('weekly_evals')
    
    op.drop_index('ix_plan_targets_effective_from', table_name='plan_targets')
    op.drop_table('plan_targets')
    
    op.drop_index('ix_strava_activities_start_date', table_name='strava_activities')
    op.drop_index('ix_strava_activities_week_id', table_name='strava_activities')
    op.drop_index('ix_strava_activities_strava_id', table_name='strava_activities')
    op.drop_table('strava_activities')
    
    op.drop_index('ix_weekly_measurements_week_start', table_name='weekly_measurements')
    op.drop_table('weekly_measurements')
    
    op.drop_index('ix_daily_logs_week_id', table_name='daily_logs')
    op.drop_index('ix_daily_logs_log_date', table_name='daily_logs')
    op.drop_table('daily_logs')