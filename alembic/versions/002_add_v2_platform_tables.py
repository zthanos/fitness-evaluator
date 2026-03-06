"""Add V2 platform tables for chat, RAG, and enhanced features

Revision ID: 002
Revises: 001
Create Date: 2024-01-15

This migration adds tables required for the Fitness Platform V2:
- athletes: Core athlete profile table
- chat_sessions: Conversation threads
- chat_messages: Individual messages within sessions
- activity_analyses: AI-generated activity effort analyses
- faiss_metadata: Vector index metadata for RAG system
- strava_tokens: Encrypted OAuth tokens for Strava integration

Also adds foreign key constraints and indexes for performance.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create new tables for V2 platform features."""
    
    # Athletes table - core profile table
    op.create_table(
        'athletes',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('current_plan', sa.Text(), nullable=True),
        sa.Column('goals', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_athletes_email', 'athletes', ['email'])
    
    # Chat sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE')
    )
    op.create_index('ix_chat_sessions_athlete_id', 'chat_sessions', ['athlete_id'])
    op.create_index('ix_chat_sessions_created_at', 'chat_sessions', ['created_at'])
    
    # Chat messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.CheckConstraint("role IN ('user', 'assistant')", name='check_message_role')
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])
    
    # Activity analyses table
    op.create_table(
        'activity_analyses',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('activity_id', sa.String(length=36), nullable=False),
        sa.Column('analysis_text', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['activity_id'], ['strava_activities.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('activity_id', name='uq_activity_analyses_activity_id')
    )
    op.create_index('ix_activity_analyses_activity_id', 'activity_analyses', ['activity_id'])
    op.create_index('ix_activity_analyses_generated_at', 'activity_analyses', ['generated_at'])
    
    # FAISS metadata table for RAG system
    op.create_table(
        'faiss_metadata',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('vector_id', sa.Integer(), nullable=False),
        sa.Column('record_type', sa.String(length=50), nullable=False),
        sa.Column('record_id', sa.String(length=255), nullable=False),
        sa.Column('embedding_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vector_id', name='uq_faiss_metadata_vector_id'),
        sa.CheckConstraint("record_type IN ('activity', 'metric', 'log', 'evaluation')", name='check_record_type')
    )
    op.create_index('ix_faiss_metadata_vector_id', 'faiss_metadata', ['vector_id'])
    op.create_index('ix_faiss_metadata_record_type', 'faiss_metadata', ['record_type'])
    op.create_index('ix_faiss_metadata_record_id', 'faiss_metadata', ['record_id'])
    op.create_index('ix_faiss_metadata_created_at', 'faiss_metadata', ['created_at'])
    
    # Strava tokens table for OAuth credentials
    op.create_table(
        'strava_tokens',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('access_token_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('refresh_token_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('athlete_id', name='uq_strava_tokens_athlete_id')
    )
    op.create_index('ix_strava_tokens_athlete_id', 'strava_tokens', ['athlete_id'])
    op.create_index('ix_strava_tokens_expires_at', 'strava_tokens', ['expires_at'])


def downgrade() -> None:
    """Drop V2 platform tables in reverse order."""
    
    # Drop tables with foreign key dependencies first
    op.drop_index('ix_strava_tokens_expires_at', table_name='strava_tokens')
    op.drop_index('ix_strava_tokens_athlete_id', table_name='strava_tokens')
    op.drop_table('strava_tokens')
    
    op.drop_index('ix_faiss_metadata_created_at', table_name='faiss_metadata')
    op.drop_index('ix_faiss_metadata_record_id', table_name='faiss_metadata')
    op.drop_index('ix_faiss_metadata_record_type', table_name='faiss_metadata')
    op.drop_index('ix_faiss_metadata_vector_id', table_name='faiss_metadata')
    op.drop_table('faiss_metadata')
    
    op.drop_index('ix_activity_analyses_generated_at', table_name='activity_analyses')
    op.drop_index('ix_activity_analyses_activity_id', table_name='activity_analyses')
    op.drop_table('activity_analyses')
    
    op.drop_index('ix_chat_messages_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    
    op.drop_index('ix_chat_sessions_created_at', table_name='chat_sessions')
    op.drop_index('ix_chat_sessions_athlete_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')
    
    op.drop_index('ix_athletes_email', table_name='athletes')
    op.drop_table('athletes')
