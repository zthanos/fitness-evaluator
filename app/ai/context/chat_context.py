"""Chat context builder for coach chat operations."""

from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.context.builder import ContextBuilder
from app.ai.retrieval.intent_router import Intent, IntentRouter
from app.ai.retrieval.rag_retriever import RAGRetriever


class ChatContextBuilder(ContextBuilder):
    """Context builder for coach chat operations."""
    
    def __init__(
        self,
        db: Session,
        token_budget: int = 2400
    ):
        """
        Initialize chat context builder.
        
        Args:
            db: SQLAlchemy database session
            token_budget: Maximum token count for context (default: 2400)
        """
        super().__init__(token_budget)
        self.db = db
        self.intent_router = IntentRouter()
        self.rag_retriever = RAGRetriever(db)
    
    def gather_data(
        self,
        query: str,
        athlete_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> 'ChatContextBuilder':
        """
        Gather data for chat response using intent-aware retrieval.
        
        Args:
            query: User query string
            athlete_id: Athlete ID for filtering
            conversation_history: Optional list of previous messages
                                 Format: [{"role": "user"|"assistant", "content": "..."}]
        
        Returns:
            Self for method chaining
        """
        # Classify query intent
        intent = self.intent_router.classify(query)
        
        # Retrieve relevant data using intent-specific policy
        retrieved_data = self.rag_retriever.retrieve(
            query=query,
            athlete_id=athlete_id,
            intent=intent,
            generate_cards=True  # Generate evidence cards
        )
        
        # Add retrieved data to context
        self.add_retrieved_data(retrieved_data)
        
        # Add conversation history if provided
        if conversation_history:
            self.add_conversation_history(conversation_history)
        
        return self
