"""PostgreSQL migration: keycloak_sub on athletes, vector_embeddings table

Revision ID: 010
Revises: 009
Create Date: 2026-04-24

Changes:
  1. athletes — add keycloak_sub column (nullable, unique)
  2. vector_embeddings — new table replacing faiss_metadata for pgvector
  3. pgvector IVFFlat index on embedding column (PostgreSQL only)

The faiss_metadata table is left intact so SQLite installs can keep
running against migration 009 without issues.
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # ── 1. athletes.keycloak_sub ──────────────────────────────────────────
    op.add_column(
        "athletes",
        sa.Column("keycloak_sub", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_athletes_keycloak_sub",
        "athletes",
        ["keycloak_sub"],
        unique=True,
    )

    # ── 2. vector_embeddings table (PostgreSQL only) ───────────────────────
    if _is_postgres():
        # Ensure pgvector extension exists (idempotent)
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

        op.create_table(
            "vector_embeddings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("athletes.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("record_type", sa.String(50), nullable=False),
            sa.Column("record_id", sa.String(150), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            # pgvector column — 768 dims for nomic-embed-text
            sa.Column("embedding", sa.Text(), nullable=False),  # placeholder; altered below
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )

        # ALTER the embedding column to the native vector type
        op.execute("ALTER TABLE vector_embeddings ALTER COLUMN embedding TYPE vector(768) USING embedding::vector")

        # Composite btree index for user-scoped queries
        op.create_index(
            "ix_vector_embeddings_user_type",
            "vector_embeddings",
            ["user_id", "record_type"],
        )

        # IVFFlat approximate nearest-neighbour index (cosine)
        # lists=100 is a sensible default; tune based on dataset size
        op.execute(
            "CREATE INDEX ix_vector_embeddings_embedding "
            "ON vector_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )


def downgrade() -> None:
    op.drop_index("ix_athletes_keycloak_sub", table_name="athletes")
    op.drop_column("athletes", "keycloak_sub")

    if _is_postgres():
        op.drop_index("ix_vector_embeddings_embedding", table_name="vector_embeddings")
        op.drop_index("ix_vector_embeddings_user_type", table_name="vector_embeddings")
        op.drop_table("vector_embeddings")
