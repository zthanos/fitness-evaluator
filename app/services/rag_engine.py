"""RAG Engine with Two-Layer Context Retrieval

Implements the Context-Engineered Chat architecture with:
- Layer 1: Active Session Buffer (in-memory storage of current session)
- Layer 2: Vector Store (FAISS + SQLite for historical semantic search)

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 20.1
"""
import logging
import os
import numpy as np
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available")

from app.models.chat_message import ChatMessage
from app.models.faiss_metadata import FaissMetadata
from app.config import get_settings


class RAGEngine:
    """
    RAG Engine for two-layer context retrieval.
    
    Layer 1: Active Session Buffer (in-memory)
    Layer 2: Vector Store (FAISS + SQLite)
    
    All vector queries are scoped to user_id for security (Requirement 20.1).
    """
    
    # Model configuration
    EMBEDDING_DIM = 768
    
    def __init__(self, db: Session, index_path: str = "data/chat_faiss_index.bin", embedding_endpoint: str = None, embedding_model: str = None):
        """
        Initialize RAG engine with vector store and active buffer.
        
        Args:
            db: SQLAlchemy database session
            index_path: Path to FAISS index file
            embedding_endpoint: Embedding API endpoint (default: from config)
            embedding_model: Embedding model name (default: from config)
        """
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is not available. Install with: pip install faiss-cpu")
        
        self.db = db
        self.index_path = index_path
        
        # Get settings from config
        settings = get_settings()
        self.embedding_type = settings.embedding_type
        self.embedding_endpoint = embedding_endpoint or settings.embedding_endpoint
        self.embedding_model = embedding_model or settings.EMBEDDING_MODEL
        self.embedding_timeout = settings.EMBEDDING_TIMEOUT
        
        logger.debug("Initializing: type=%s endpoint=%s model=%s dim=%d",
                     self.embedding_type, self.embedding_endpoint,
                     self.embedding_model, self.EMBEDDING_DIM)
        
        # Initialize or load FAISS index
        self.index = None
        self.load_index()
    
    def generate_embedding(self, text: str, max_length: int = 2048) -> np.ndarray:
        """
        Generate embedding for text using configured embedding backend.
        
        Supports both Ollama-style API (/api/embeddings) and OpenAI-style API (/v1/embeddings).
        
        Args:
            text: Input text
            max_length: Maximum text length in characters (default: 2048)
        
        Returns:
            768-dimensional embedding vector (L2-normalized)
        """
        # Truncate text if too long
        if len(text) > max_length:
            text = text[:max_length]
            logger.debug("Truncated embedding text to %d characters", max_length)
        
        try:
            # Determine API style and endpoint based on embedding type
            if self.embedding_type == "ollama":
                # Ollama-style API: POST /api/embeddings
                url = f"{self.embedding_endpoint}/api/embeddings"
                payload = {
                    "model": self.embedding_model,
                    "prompt": text
                }
            else:
                # OpenAI-style API (LM Studio): POST /v1/embeddings
                url = f"{self.embedding_endpoint}/v1/embeddings"
                payload = {
                    "model": self.embedding_model,
                    "input": text
                }
            
            # Call embedding API
            response = httpx.post(
                url,
                json=payload,
                timeout=self.embedding_timeout
            )
            response.raise_for_status()
            
            # Extract embedding from response
            data = response.json()
            
            # Handle different response formats
            if self.embedding_type == "ollama":
                # Ollama returns: {"embedding": [...]}
                embedding = np.array(data["embedding"], dtype='float32')
            else:
                # OpenAI-style returns: {"data": [{"embedding": [...]}]}
                embedding = np.array(data["data"][0]["embedding"], dtype='float32')
            
            # L2-normalize for cosine similarity (Requirement 1.6)
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding
            
        except httpx.HTTPError as e:
            logger.error("HTTP error generating embedding: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error generating embedding: %s", e)
            raise
    
    def initialize_index(self) -> None:
        """Create a new FAISS index."""
        logger.info("Creating new FAISS index (dim=%d)", self.EMBEDDING_DIM)
        
        # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
        self.index = faiss.IndexFlatIP(self.EMBEDDING_DIM)
        
        # Clear chat message metadata from database
        self.db.query(FaissMetadata).filter(
            FaissMetadata.record_type == 'chat_message'
        ).delete()
        self.db.commit()
    
    def load_index(self) -> None:
        """Load FAISS index from disk."""
        if os.path.exists(self.index_path):
            try:
                logger.info("Loading FAISS index from %s", self.index_path)
                self.index = faiss.read_index(self.index_path)
                metadata_count = self.db.query(FaissMetadata).filter(
                    FaissMetadata.record_type == 'chat_message'
                ).count()
                logger.info("Loaded index: %d vectors, %d chat records", self.index.ntotal, metadata_count)
            except Exception as e:
                logger.error("Error loading index, reinitializing: %s", e)
                self.initialize_index()
        else:
            logger.info("No existing index found, creating new one")
            self.initialize_index()
    
    def save_index(self) -> None:
        """Save FAISS index to disk."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            
            # Save index
            faiss.write_index(self.index, self.index_path)
            
            # Commit metadata to database
            self.db.commit()
            
            logger.info("Saved index: %d vectors -> %s", self.index.ntotal, self.index_path)
        except Exception as e:
            logger.error("Error saving index: %s", e)
            self.db.rollback()
    
    def search_similar(
        self, 
        query_embedding: np.ndarray, 
        user_id: int, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search vector store with user_id filter.
        
        Args:
            query_embedding: Query embedding vector (768-dim, L2-normalized)
            user_id: User ID for scoping (Requirement 20.1)
            top_k: Number of results to return
        
        Returns:
            List of dicts with: message_id, text, similarity, date, session_id, eval_score
        """
        # Validate user_id is present (Requirement 20.1)
        if user_id is None:
            logger.error("SECURITY VIOLATION: user_id is None in search_similar")
            raise ValueError("user_id is required for vector search")

        if self.index.ntotal == 0:
            logger.debug("Index is empty, returning no results")
            return []
        
        # Search index (get more results than needed for filtering)
        search_k = min(top_k * 10, self.index.ntotal)
        similarities, indices = self.index.search(
            np.array([query_embedding]), 
            search_k
        )
        
        # Filter by user_id and build results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0:  # Valid index
                # Retrieve metadata from database with user_id filter
                metadata = self.db.query(FaissMetadata).filter(
                    FaissMetadata.vector_id == int(idx),
                    FaissMetadata.record_type == 'chat_message',
                    FaissMetadata.user_id == user_id  # CRITICAL: User scoping
                ).first()
                
                if metadata:
                    # Verify user_id matches (additional security check)
                    if metadata.user_id != user_id:
                        logger.error(
                            "SECURITY VIOLATION: cross-user access attempt - "
                            "requested=%d found=%d vector=%d", user_id, metadata.user_id, idx
                        )
                        continue
                    
                    # Parse key format: chat:{user_id}:{session_id}:{date}:eval_{score}
                    key_parts = metadata.record_id.split(':')
                    session_id = key_parts[2] if len(key_parts) > 2 else None
                    date_str = key_parts[3] if len(key_parts) > 3 else None
                    eval_score = float(key_parts[4].replace('eval_', '')) if len(key_parts) > 4 and key_parts[4].startswith('eval_') else 0.0
                    
                    results.append({
                        'message_id': metadata.id,
                        'text': metadata.embedding_text,
                        'similarity': float(similarities[0][i]),
                        'date': date_str,
                        'session_id': session_id,
                        'eval_score': eval_score
                    })
                    
                    # Stop when we have enough results
                    if len(results) >= top_k:
                        break
        
        logger.debug("Search returned %d results for user_id=%d", len(results), user_id)
        return results

    
    def retrieve_context(
        self, 
        query: str, 
        user_id: int, 
        active_session_messages: List[ChatMessage],
        top_k: int = 5
    ) -> str:
        """
        Retrieve context from both layers.
        
        Layer 1: Active Session Buffer (current session messages)
        Layer 2: Vector Store (historical semantic search)
        
        Args:
            query: User's current message
            user_id: Requesting user ID (for scoping)
            active_session_messages: Current session messages
            top_k: Number of similar messages to retrieve from vector store
            
        Returns:
            Formatted context string combining both layers
            
        Requirements: 1.1, 1.2, 1.3, 17.2, 20.1
        """
        import time
        start_time = time.time()
        
        # Validate user_id is present (Requirement 20.1)
        if user_id is None:
            logger.error("SECURITY VIOLATION: user_id is None in retrieve_context")
            raise ValueError("user_id is required for context retrieval")
        
        context_parts = []
        
        # Layer 1: Active Session Buffer (Requirement 1.1)
        if active_session_messages:
            context_parts.append("=== Current Session ===")
            # Include last 10 messages for immediate context
            for msg in active_session_messages[-10:]:
                context_parts.append(f"{msg.role}: {msg.content}")
        
        # Layer 2: Vector Store (Requirement 1.2)
        vector_start_time = time.time()
        try:
            query_embedding = self.generate_embedding(query)
            similar_messages = self.search_similar(
                query_embedding=query_embedding,
                user_id=user_id,  # CRITICAL: User scoping (Requirement 20.1)
                top_k=top_k
            )
            
            vector_latency_ms = (time.time() - vector_start_time) * 1000
            logger.debug("Vector retrieval: %dms for user_id=%d", vector_latency_ms, user_id)
            if vector_latency_ms > 500:
                logger.warning("Vector retrieval exceeded 500ms target: %dms", vector_latency_ms)
            
            if similar_messages:
                context_parts.append("\n=== Relevant Past Conversations ===")
                for msg in similar_messages:
                    date_str = msg.get('date', 'unknown')
                    eval_score = msg.get('eval_score', 0.0)
                    context_parts.append(
                        f"[{date_str}, score: {eval_score:.1f}] {msg['text']}"
                    )
        except httpx.TimeoutException:
            logger.warning("Embedding service timed out after %ds - continuing with session buffer only", self.embedding_timeout)
        except Exception as e:
            logger.warning("Vector store unavailable (%s) - continuing with session buffer only", type(e).__name__)

        total_latency_ms = (time.time() - start_time) * 1000
        logger.debug("Context retrieval completed in %dms", total_latency_ms)
        
        return "\n".join(context_parts)
    
    def persist_session(
        self, 
        user_id: int, 
        session_id: int, 
        messages: List[ChatMessage],
        eval_score: Optional[float] = None
    ) -> None:
        """
        Persist session messages to vector store.
        
        Key format: chat:{user_id}:{session_id}:{date}:eval_{score}
        
        Args:
            user_id: User ID
            session_id: Session ID
            messages: List of chat messages to persist
            eval_score: Optional evaluation score for the session
            
        Requirements: 1.4, 1.5, 1.6, 20.1
        """
        # Validate user_id is present (Requirement 20.1)
        if user_id is None:
            logger.error("SECURITY VIOLATION: user_id is None in persist_session")
            raise ValueError("user_id is required for session persistence")

        if not messages:
            logger.debug("No messages to persist for session %d", session_id)
            return
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        score_str = f"eval_{eval_score:.1f}" if eval_score else "eval_0.0"
        
        persisted_count = 0
        for msg in messages:
            try:
                # Generate embedding
                embedding = self.generate_embedding(msg.content)
                
                # Create key (Requirement 1.5)
                key = f"chat:{user_id}:{session_id}:{date_str}:{score_str}"
                
                # Get the next vector ID
                vector_id = self.index.ntotal
                
                # Add to FAISS index (Requirement 1.6)
                self.index.add(np.array([embedding]))
                
                # Store metadata in database with user_id (Requirement 20.1)
                metadata = FaissMetadata(
                    vector_id=vector_id,
                    record_type='chat_message',
                    record_id=key,  # Store key in record_id field
                    embedding_text=msg.content,
                    user_id=user_id  # CRITICAL: User scoping
                )
                self.db.add(metadata)
                
                persisted_count += 1
                
            except Exception as e:
                logger.warning("Skipping message %s (embedding failed): %s", msg.id, e)
                continue

        try:
            self.save_index()
            logger.info("Persisted %d/%d messages for session %d", persisted_count, len(messages), session_id)
        except Exception as e:
            logger.error("Error saving index after persist_session: %s", e)
            self.db.rollback()
    
    def delete_session(self, user_id: int, session_id: int) -> None:
        """
        Remove session from vector store and database.
        
        Uses prefix match on key pattern: chat:{user_id}:{session_id}:*
        
        Args:
            user_id: User ID
            session_id: Session ID
            
        Requirements: 2.1, 2.2, 2.3, 2.4, 20.1
        """
        # Validate user_id is present (Requirement 20.1)
        if user_id is None:
            logger.error("SECURITY VIOLATION: user_id is None in delete_session")
            raise ValueError("user_id is required for session deletion")
        
        try:
            # Find all metadata records for this session
            key_prefix = f"chat:{user_id}:{session_id}:"
            
            metadata_records = self.db.query(FaissMetadata).filter(
                FaissMetadata.record_type == 'chat_message',
                FaissMetadata.user_id == user_id,
                FaissMetadata.record_id.like(f"{key_prefix}%")
            ).all()
            
            if not metadata_records:
                logger.debug("No metadata found for session %d", session_id)
                return
            
            # Get vector IDs to remove
            vector_ids = [m.vector_id for m in metadata_records]
            
            # Delete metadata from database
            for metadata in metadata_records:
                self.db.delete(metadata)
            
            # Note: FAISS doesn't support efficient deletion of individual vectors
            # We mark them as deleted in metadata, and they'll be filtered out in search
            # A full rebuild would be needed to actually remove them from the index
            
            self.db.commit()
            
            logger.info("Deleted %d messages for session %d", len(metadata_records), session_id)

        except Exception as e:
            logger.error("Error deleting session %d: %s", session_id, e)
            self.db.rollback()
            raise
