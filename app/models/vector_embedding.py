"""VectorEmbedding model — replaces FaissMetadata for pgvector-backed RAG."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.models.base import Base

EMBEDDING_DIM = 768


class VectorEmbedding(Base):
    """
    Stores text embeddings alongside their source metadata.

    Replaces the old FaissMetadata + on-disk FAISS index approach.
    Similarity search is performed directly in PostgreSQL via the
    pgvector '<->' (L2) or '<=>' (cosine) operators.

    user_id scoping ensures every query is restricted to a single
    athlete's data (Requirement 20.1).
    """

    __tablename__ = "vector_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    record_type = Column(String(50), nullable=False)   # chat_message | activity | metric | log
    record_id = Column(String(150), nullable=False)    # opaque key, format varies by type
    content = Column(Text, nullable=False)             # the text that was embedded
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        # Index for fast user-scoped lookups
        Index("ix_vector_embeddings_user_type", "user_id", "record_type"),
        # pgvector IVFFlat index for approximate nearest-neighbour search.
        # Created in the Alembic migration so we can pass lists= parameter.
        # Index("ix_vector_embeddings_embedding", "embedding", ...),  # see migration
    )

    def __repr__(self) -> str:
        return (
            f"<VectorEmbedding(id={self.id}, user_id={self.user_id}, "
            f"type={self.record_type}, record_id={self.record_id})>"
        )
