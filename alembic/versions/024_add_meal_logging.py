"""add meal logging tables

Revision ID: 024
Revises: 023
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'meals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('athlete_id', sa.Integer, sa.ForeignKey('athletes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('log_date', sa.Date, nullable=False),
        sa.Column('meal_type', sa.String(20), nullable=False),
        sa.Column('name', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name='check_meal_type'
        ),
    )
    op.create_index('ix_meals_log_date', 'meals', ['log_date'])

    op.create_table(
        'meal_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('meal_id', sa.String(36), sa.ForeignKey('meals.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('quantity', sa.Float, nullable=True),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('calories', sa.Float, nullable=True),
        sa.Column('protein_g', sa.Float, nullable=True),
        sa.Column('carbs_g', sa.Float, nullable=True),
        sa.Column('fat_g', sa.Float, nullable=True),
        sa.Column('source', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('confidence', sa.Float, nullable=False, server_default='1.0'),
        sa.Column('needs_confirmation', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('source_ref', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "source IN ('manual', 'ai', 'product_search', 'template')",
            name='check_meal_item_source'
        ),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='check_meal_item_confidence'),
    )

    op.create_table(
        'meal_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('athlete_id', sa.Integer, sa.ForeignKey('athletes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('meal_type', sa.String(20), nullable=True),
        sa.Column('items_json', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "meal_type IS NULL OR meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name='check_template_meal_type'
        ),
    )


def downgrade():
    op.drop_table('meal_templates')
    op.drop_index('ix_meals_log_date', table_name='meals')
    op.drop_table('meal_items')
    op.drop_table('meals')
