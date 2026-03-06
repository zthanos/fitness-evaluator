"""Update daily log constraints for Requirements 8.2

Revision ID: 005
Revises: 004
Create Date: 2024-01-15

Updates:
- Change adherence_score range from 1-10 to 0-100
- Add validation constraints for calories (0-10000)
- Add validation constraints for macros (0-1000g each)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    """Update daily_logs table constraints."""
    
    # SQLite requires batch mode for constraint modifications
    with op.batch_alter_table('daily_logs', schema=None) as batch_op:
        # Drop old constraint
        batch_op.drop_constraint('check_adherence_score_range', type_='check')
        
        # Add new constraints per Requirements 8.2
        batch_op.create_check_constraint(
            'check_adherence_score_range',
            'adherence_score >= 0 AND adherence_score <= 100'
        )
        
        batch_op.create_check_constraint(
            'check_calories_range',
            'calories_in >= 0 AND calories_in <= 10000'
        )
        
        batch_op.create_check_constraint(
            'check_protein_range',
            'protein_g >= 0 AND protein_g <= 1000'
        )
        
        batch_op.create_check_constraint(
            'check_carbs_range',
            'carbs_g >= 0 AND carbs_g <= 1000'
        )
        
        batch_op.create_check_constraint(
            'check_fat_range',
            'fat_g >= 0 AND fat_g <= 1000'
        )


def downgrade():
    """Revert daily_logs table constraints."""
    
    # SQLite requires batch mode for constraint modifications
    with op.batch_alter_table('daily_logs', schema=None) as batch_op:
        # Drop new constraints
        batch_op.drop_constraint('check_fat_range', type_='check')
        batch_op.drop_constraint('check_carbs_range', type_='check')
        batch_op.drop_constraint('check_protein_range', type_='check')
        batch_op.drop_constraint('check_calories_range', type_='check')
        batch_op.drop_constraint('check_adherence_score_range', type_='check')
        
        # Restore old constraint
        batch_op.create_check_constraint(
            'check_adherence_score_range',
            'adherence_score >= 1 AND adherence_score <= 10'
        )
