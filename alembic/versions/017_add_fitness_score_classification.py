"""Add fitness_score and athlete_classification to athlete_fitness_states

Revision ID: 017
Revises: 016
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('athlete_fitness_states',
                  sa.Column('fitness_score', sa.Float(), nullable=True))
    op.add_column('athlete_fitness_states',
                  sa.Column('athlete_classification', sa.String(100), nullable=True))


def downgrade():
    op.drop_column('athlete_fitness_states', 'athlete_classification')
    op.drop_column('athlete_fitness_states', 'fitness_score')
