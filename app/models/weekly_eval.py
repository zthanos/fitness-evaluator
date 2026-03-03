from datetime import datetime
from sqlalchemy import Column, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import Base, TimestampMixin
import uuid

class WeeklyEval(Base, TimestampMixin):
    __tablename__ = 'weekly_evals'
    
    id: uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_id: uuid.UUID = Column(PG_UUID(as_uuid=True), nullable=False)
    input_hash: str = Column(String(64), nullable=False)
    llm_model: str = Column(String(100), nullable=True)
    raw_llm_response: str = Column(String, nullable=True)
    parsed_output_json: dict = Column(JSON, nullable=True)
    generated_at: datetime = Column(DateTime, nullable=True)
    evidence_map_json: dict = Column(JSON, nullable=True)
    
    # Add unique constraint for week_id
    __table_args__ = (
        UniqueConstraint('week_id'),
    )
