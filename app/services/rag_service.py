"""RAG (Retrieval Augmented Generation) Service

Manages FAISS vector index for semantic search across athlete data.
Generates embeddings using Ollama's nomic-embed-text model.
Provides context retrieval for AI coach chat.

Migrated to Context Engineering architecture with:
- IntentRouter for query classification
- RAGRetriever for intent-based data retrieval
- Evidence card generation for traceability
"""
import os
import pickle
import numpy as np
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("[RAG] FAISS not available")

from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.models.weekly_eval import WeeklyEval
from app.models.faiss_metadata import FaissMetadata

# Context Engineering imports
from app.ai.retrieval.intent_router import IntentRouter, Intent
from app.ai.retrieval.rag_retriever import RAGRetriever


class RAGSystem:
    """
    RAG system for semantic search across athlete data.
    
    Uses:
    - Ollama's nomic-embed-text model for 768-dimensional embeddings
    - FAISS for efficient vector similarity search
    - SQLite for metadata storage
    """
    
    # Model configuration
    MODEL_NAME = "nomic-embed-text"
    EMBEDDING_DIM = 768
    OLLAMA_ENDPOINT = "http://localhost:11434"
    
    def __init__(self, db: Session, index_path: str = "data/faiss_index.bin", ollama_endpoint: str = None):
        """
        Initialize RAG system.
        
        Args:
            db: SQLAlchemy database session
            index_path: Path to FAISS index file
            ollama_endpoint: Ollama API endpoint (default: http://localhost:11434)
        """
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is not available. Install with: pip install faiss-cpu")
        
        self.db = db
        self.index_path = index_path
        self.ollama_endpoint = ollama_endpoint or self.OLLAMA_ENDPOINT
        
        # Log initialization
        print(f"[RAG] Initializing with Ollama endpoint: {self.ollama_endpoint}")
        print(f"[RAG] Using embedding model: {self.MODEL_NAME}")
        print(f"[RAG] Embedding dimension: {self.EMBEDDING_DIM}")
        
        # Initialize or load FAISS index
        self.index = None
        
        self.load_index()
        
        # Initialize Context Engineering components
        self.intent_router = IntentRouter()
        self.rag_retriever = RAGRetriever(db)
    
    def generate_embedding(self, text: str, max_length: int = 2048) -> np.ndarray:
        """
        Generate embedding for text using Ollama's nomic-embed-text model.
        
        Args:
            text: Input text
            max_length: Maximum text length in characters (default: 2048)
        
        Returns:
            768-dimensional embedding vector
        """
        # Truncate text if too long to avoid Ollama errors
        if len(text) > max_length:
            text = text[:max_length]
            print(f"[RAG] Truncated text to {max_length} characters")
        
        try:
            # Call Ollama API for embeddings
            response = httpx.post(
                f"{self.ollama_endpoint}/api/embeddings",
                json={
                    "model": self.MODEL_NAME,
                    "prompt": text
                },
                timeout=30.0
            )
            response.raise_for_status()
            
            # Extract embedding from response
            data = response.json()
            embedding = np.array(data["embedding"], dtype='float32')
            
            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding
            
        except httpx.HTTPError as e:
            print(f"[RAG] Error generating embedding: {e}")
            raise
        except Exception as e:
            print(f"[RAG] Unexpected error generating embedding: {e}")
            raise
    
    def initialize_index(self) -> None:
        """Create a new FAISS index."""
        print(f"[RAG] Creating new FAISS index (dim={self.EMBEDDING_DIM})")
        
        # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
        self.index = faiss.IndexFlatIP(self.EMBEDDING_DIM)
        
        # Clear metadata from database
        self.db.query(FaissMetadata).delete()
        self.db.commit()
    
    def load_index(self) -> None:
        """Load FAISS index from disk."""
        if os.path.exists(self.index_path):
            try:
                print(f"[RAG] Loading FAISS index from {self.index_path}")
                self.index = faiss.read_index(self.index_path)
                
                # Metadata is stored in database, no need to load from pickle
                metadata_count = self.db.query(FaissMetadata).count()
                
                print(f"[RAG] Loaded index with {self.index.ntotal} vectors and {metadata_count} metadata records")
            except Exception as e:
                print(f"[RAG] Error loading index: {e}")
                self.initialize_index()
        else:
            print("[RAG] No existing index found, creating new one")
            self.initialize_index()
    
    def save_index(self) -> None:
        """Save FAISS index to disk."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            
            # Save index
            faiss.write_index(self.index, self.index_path)
            
            # Metadata is stored in database, commit the transaction
            self.db.commit()
            
            print(f"[RAG] Saved index with {self.index.ntotal} vectors to {self.index_path}")
        except Exception as e:
            print(f"[RAG] Error saving index: {e}")
            self.db.rollback()
    
    def index_activity(self, activity: StravaActivity) -> None:
        """
        Index a Strava activity.
        
        Args:
            activity: StravaActivity model instance
        """
        # Format activity text
        text = self._format_activity_text(activity)
        
        # Generate embedding
        embedding = self.generate_embedding(text)
        
        # Get the next vector ID
        vector_id = self.index.ntotal
        
        # Add to index
        self.index.add(np.array([embedding]))
        
        # Store metadata in database
        metadata = FaissMetadata(
            vector_id=vector_id,
            record_type='activity',
            record_id=str(activity.id),
            embedding_text=text
        )
        self.db.add(metadata)
        
        print(f"[RAG] Indexed activity {activity.id} as vector {vector_id}")
    
    def index_metric(self, metric: WeeklyMeasurement) -> None:
        """
        Index a body metric.
        
        Args:
            metric: WeeklyMeasurement model instance
        """
        # Format metric text
        text = self._format_metric_text(metric)
        
        # Generate embedding
        embedding = self.generate_embedding(text)
        
        # Get the next vector ID
        vector_id = self.index.ntotal
        
        # Add to index
        self.index.add(np.array([embedding]))
        
        # Store metadata in database
        metadata = FaissMetadata(
            vector_id=vector_id,
            record_type='metric',
            record_id=str(metric.id),
            embedding_text=text
        )
        self.db.add(metadata)
        
        print(f"[RAG] Indexed metric {metric.id} as vector {vector_id}")
    
    def index_log(self, log: DailyLog) -> None:
        """
        Index a daily log.
        
        Args:
            log: DailyLog model instance
        """
        # Format log text
        text = self._format_log_text(log)
        
        # Generate embedding
        embedding = self.generate_embedding(text)
        
        # Get the next vector ID
        vector_id = self.index.ntotal
        
        # Add to index
        self.index.add(np.array([embedding]))
        
        # Store metadata in database
        metadata = FaissMetadata(
            vector_id=vector_id,
            record_type='log',
            record_id=str(log.id),
            embedding_text=text
        )
        self.db.add(metadata)
        
        print(f"[RAG] Indexed log {log.id} as vector {vector_id}")
    
    def index_evaluation(self, evaluation: WeeklyEval) -> None:
        """
        Index an evaluation report.
        
        Args:
            evaluation: WeeklyEval model instance
        """
        # Format evaluation text
        text = self._format_evaluation_text(evaluation)
        
        # Generate embedding
        embedding = self.generate_embedding(text)
        
        # Get the next vector ID
        vector_id = self.index.ntotal
        
        # Add to index
        self.index.add(np.array([embedding]))
        
        # Store metadata in database
        metadata = FaissMetadata(
            vector_id=vector_id,
            record_type='evaluation',
            record_id=str(evaluation.id),
            embedding_text=text
        )
        self.db.add(metadata)
        
        print(f"[RAG] Indexed evaluation {evaluation.id} as vector {vector_id}")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant records.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of dicts with record_type, record_id, text, similarity
        """
        if self.index.ntotal == 0:
            print("[RAG] Index is empty, returning no results")
            return []
        
        # Generate query embedding
        query_embedding = self.generate_embedding(query)
        
        # Search index
        similarities, indices = self.index.search(np.array([query_embedding]), top_k)
        
        # Build results by retrieving metadata from database
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0:  # Valid index
                # Retrieve metadata from database
                metadata = self.db.query(FaissMetadata).filter(FaissMetadata.vector_id == int(idx)).first()
                
                if metadata:
                    results.append({
                        'record_type': metadata.record_type,
                        'record_id': metadata.record_id,
                        'text': metadata.embedding_text,
                        'similarity': float(similarities[0][i])
                    })
        
        print(f"[RAG] Search for '{query[:50]}...' returned {len(results)} results")
        return results
    
    def _format_activity_text(self, activity: StravaActivity) -> str:
        """Format activity for embedding."""
        # Note: StravaActivity doesn't have a 'name' field, using activity_type instead
        parts = [
            f"Activity Type: {activity.activity_type}",
            f"Date: {activity.start_date.strftime('%Y-%m-%d')}",
            f"Distance: {activity.distance_m / 1000:.2f} km" if activity.distance_m else "",
            f"Duration: {activity.moving_time_s // 60} minutes" if activity.moving_time_s else "",
            f"Elevation: {activity.elevation_m:.0f} m" if activity.elevation_m else "",
        ]
        
        return " | ".join(p for p in parts if p)
    
    def _format_metric_text(self, metric: WeeklyMeasurement) -> str:
        """Format body metric for embedding."""
        parts = [
            f"Body Measurement",
            f"Date: {metric.week_start.strftime('%Y-%m-%d')}",
            f"Weight: {metric.weight_kg:.1f} kg" if metric.weight_kg else "",
            f"Body Fat: {metric.body_fat_pct:.1f}%" if metric.body_fat_pct else "",
        ]
        
        # Add circumference measurements if available
        if metric.waist_cm:
            parts.append(f"Waist: {metric.waist_cm:.1f} cm")
        
        return " | ".join(p for p in parts if p)
    
    def _format_log_text(self, log: DailyLog) -> str:
        """Format daily log for embedding."""
        parts = [
            f"Daily Log",
            f"Date: {log.log_date.strftime('%Y-%m-%d')}",
            f"Calories: {log.calories_in}" if log.calories_in else "",
            f"Protein: {log.protein_g:.0f}g" if log.protein_g else "",
            f"Carbs: {log.carbs_g:.0f}g" if log.carbs_g else "",
            f"Fats: {log.fat_g:.0f}g" if log.fat_g else "",
            f"Adherence: {log.adherence_score}/100" if log.adherence_score is not None else "",
        ]
        
        # Add notes if available
        if log.notes:
            parts.append(f"Notes: {log.notes}")
        
        return " | ".join(p for p in parts if p)
    
    def _format_evaluation_text(self, evaluation: WeeklyEval) -> str:
        """Format evaluation for embedding."""
        parts = [
            f"Evaluation Report",
            f"Week ID: {evaluation.week_id}",
        ]
        
        # Add parsed output if available
        if evaluation.parsed_output_json:
            output = evaluation.parsed_output_json
            if 'overall_score' in output:
                parts.append(f"Score: {output['overall_score']}/100")
            if 'wins' in output:
                parts.append(f"Wins: {output['wins']}")
            if 'misses' in output:
                parts.append(f"Areas to improve: {output['misses']}")
        
        return " | ".join(p for p in parts if p)
    
    def rebuild_index(self) -> None:
        """
        Rebuild the entire index from database.
        
        This is useful for:
        - Initial index creation
        - Recovering from index corruption
        - Updating index after schema changes
        """
        print("[RAG] Rebuilding index from database...")
        
        # Initialize new index
        self.initialize_index()
        
        # Index all activities
        activities = self.db.query(StravaActivity).all()
        for activity in activities:
            self.index_activity(activity)
        
        # Index all metrics
        metrics = self.db.query(WeeklyMeasurement).all()
        for metric in metrics:
            self.index_metric(metric)
        
        # Index all logs
        logs = self.db.query(DailyLog).all()
        for log in logs:
            self.index_log(log)
        
        # Index all evaluations
        evaluations = self.db.query(WeeklyEval).all()
        for evaluation in evaluations:
            self.index_evaluation(evaluation)
        
        # Save index
        self.save_index()
        
        print(f"[RAG] Index rebuilt with {self.index.ntotal} vectors")
    
    # ========== Context Engineering Methods ==========
    
    def retrieve_with_intent(
        self,
        query: str,
        athlete_id: int,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Retrieve data using intent-aware retrieval (Context Engineering).
        
        This method replaces manual query classification with IntentRouter
        and uses retrieval_policies.yaml for intent-specific retrieval.
        
        Args:
            query: User query string
            athlete_id: Athlete ID for filtering
            top_k: Maximum number of results (default: 20)
        
        Returns:
            List of evidence card dictionaries with fields:
                - claim_text: Descriptive text about the data point
                - source_type: Type of source (activity/goal/metric/log)
                - source_id: Database record ID
                - source_date: ISO format date
                - relevance_score: Float 0.0-1.0
        
        Requirements: 5.3.3 - Use IntentRouter and retrieval_policies.yaml
        """
        # Classify query intent using IntentRouter
        intent = self.intent_router.classify(query)
        
        print(f"[RAG] Classified query intent as: {intent.value}")
        
        # Retrieve data using RAGRetriever with intent-specific policy
        evidence_cards = self.rag_retriever.retrieve(
            query=query,
            athlete_id=athlete_id,
            intent=intent,
            generate_cards=True  # Generate evidence cards per requirement 4.1.3
        )
        
        # Limit to top_k results
        evidence_cards = evidence_cards[:top_k]
        
        print(f"[RAG] Retrieved {len(evidence_cards)} evidence cards for intent {intent.value}")
        
        return evidence_cards
    
    def classify_intent(self, query: str) -> Intent:
        """
        Classify query intent using IntentRouter.
        
        Args:
            query: User query string
        
        Returns:
            Intent enum value
        
        Requirements: 5.3.3 - Use IntentRouter for query classification
        """
        return self.intent_router.classify(query)
