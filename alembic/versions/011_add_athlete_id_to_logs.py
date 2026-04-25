"""Add athlete_id to daily_logs and weekly_measurements

Revision ID: 011
Revises: 010
Create Date: 2026-04-24

Changes:
  1. daily_logs       — add athlete_id (FK → athletes.id), drop unique on log_date,
                        add unique(athlete_id, log_date)
  2. weekly_measurements — same pattern for week_start
  3. athlete_goals    — athlete_id column already exists (nullable String);
                        no schema change needed here
"""
from alembic import op
import sqlalchemy as sa


revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    # ── daily_logs ─────────────────────────────────────────────────────────
    op.add_column('daily_logs',
        sa.Column('athlete_id', sa.Integer(),
                  sa.ForeignKey('athletes.id', ondelete='CASCADE'),
                  nullable=True)
    )
    op.create_index('ix_daily_logs_athlete_id', 'daily_logs', ['athlete_id'])

    # Drop old per-date unique constraint and replace with per-athlete-per-date
    with op.batch_alter_table('daily_logs') as batch_op:
        batch_op.drop_constraint('daily_logs_log_date_key', type_='unique')
        batch_op.create_unique_constraint(
            'uq_daily_logs_athlete_date', ['athlete_id', 'log_date']
        )

    # ── weekly_measurements ────────────────────────────────────────────────
    op.add_column('weekly_measurements',
        sa.Column('athlete_id', sa.Integer(),
                  sa.ForeignKey('athletes.id', ondelete='CASCADE'),
                  nullable=True)
    )
    op.create_index('ix_weekly_measurements_athlete_id', 'weekly_measurements', ['athlete_id'])

    with op.batch_alter_table('weekly_measurements') as batch_op:
        batch_op.drop_constraint('weekly_measurements_week_start_key', type_='unique')
        batch_op.create_unique_constraint(
            'uq_weekly_measurements_athlete_week', ['athlete_id', 'week_start']
        )


def downgrade():
    with op.batch_alter_table('weekly_measurements') as batch_op:
        batch_op.drop_constraint('uq_weekly_measurements_athlete_week', type_='unique')
        batch_op.create_unique_constraint('weekly_measurements_week_start_key', ['week_start'])
    op.drop_index('ix_weekly_measurements_athlete_id', table_name='weekly_measurements')
    op.drop_column('weekly_measurements', 'athlete_id')

    with op.batch_alter_table('daily_logs') as batch_op:
        batch_op.drop_constraint('uq_daily_logs_athlete_date', type_='unique')
        batch_op.create_unique_constraint('daily_logs_log_date_key', ['log_date'])
    op.drop_index('ix_daily_logs_athlete_id', table_name='daily_logs')
    op.drop_column('daily_logs', 'athlete_id')
