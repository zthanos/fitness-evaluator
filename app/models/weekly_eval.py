from datetime import datetime
from sqlalchemy import Column, DateTime, JSON, String, UniqueConstraint
from app.models.base import Base, TimestampMixin
import uuid

class WeeklyEval(Base, TimestampMixin):
    __tablename__ = 'weekly_evals'
    
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    week_id: str = Column(String(36), nullable=False)
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
    
    @property
    def evidence_cards(self) -> list:
        """
        Get evidence cards with backward compatibility.
        
        Returns empty list if evidence_map_json is null (for old records).
        This ensures backward compatibility with existing WeeklyEval records
        that were created before evidence tracking was implemented.
        
        Returns:
            List of evidence card dictionaries
        """
        if self.evidence_map_json is None:
            return []
        return self.evidence_map_json.get("evidence_cards", [])
