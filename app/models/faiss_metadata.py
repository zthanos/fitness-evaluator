"""FAISS Metadata model for RAG system."""

from sqlalchemy import Column, Integer, String, Text, DateTime, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func
from app.models.base import Base


class FaissMetadata(Base):
    """
    FAISS Metadata model.
    
    Stores metadata mapping between FAISS vector IDs and database record IDs.
    This allows the RAG system to retrieve full record details after semantic search.
    
    The user_id column enables user-scoped vector queries for security.
    """
    
    __tablename__ = "faiss_metadata"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vector_id = Column(Integer, nullable=False, unique=True, index=True)
    record_type = Column(String(50), nullable=False, index=True)
    record_id = Column(String(100), nullable=False, index=True)
    embedding_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), index=True)
    user_id = Column(Integer, nullable=True, index=True)  # Added for user-scoped vector queries
    
    __table_args__ = (
        CheckConstraint("record_type IN ('activity', 'metric', 'log', 'evaluation', 'chat_message')", name='check_record_type'),
        UniqueConstraint('vector_id', name='uq_faiss_metadata_vector_id'),
    )
    
    def __repr__(self):
        return f"<FaissMetadata(id={self.id}, vector_id={self.vector_id}, record_type={self.record_type}, record_id={self.record_id})>"
