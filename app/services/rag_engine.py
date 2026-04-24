"""RAG Engine — pgvector-backed two-layer context retrieval.

Layer 1: Active Session Buffer (in-memory, current session)
Layer 2: Vector Store (pgvector in PostgreSQL)

Falls back to session-buffer-only mode when the embedding service is
unavailable — chat still works, just without cross-session memory.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 20.1
"""
import logging
import time
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.chat_message import ChatMessage
from app.models.vector_embedding import VectorEmbedding, EMBEDDING_DIM

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    pgvector-backed RAG engine.

    Replaces the previous FAISS + FaissMetadata implementation.
    All vector queries are scoped to user_id (Requirement 20.1).
    """

    def __init__(
        self,
        db: Session,
        embedding_endpoint: str = None,
        embedding_model: str = None,
    ):
        settings = get_settings()
        self.db = db
        self.embedding_type = settings.embedding_type
        self.embedding_endpoint = embedding_endpoint or settings.embedding_endpoint
        self.embedding_model = embedding_model or settings.EMBEDDING_MODEL
        self.embedding_timeout = settings.EMBEDDING_TIMEOUT

        logger.debug(
            "RAGEngine init: type=%s endpoint=%s model=%s dim=%d",
            self.embedding_type, self.embedding_endpoint,
            self.embedding_model, EMBEDDING_DIM,
        )

    # ── Embedding generation ───────────────────────────────────────────────

    def generate_embedding(self, text: str, max_length: int = 2048) -> np.ndarray:
        """Call the configured embedding API and return a normalised vector."""
        if len(text) > max_length:
            text = text[:max_length]
            logger.debug("Truncated embedding text to %d chars", max_length)

        if self.embedding_type == "ollama":
            url = f"{self.embedding_endpoint}/api/embeddings"
            payload = {"model": self.embedding_model, "prompt": text}
        else:
            url = f"{self.embedding_endpoint}/v1/embeddings"
            payload = {"model": self.embedding_model, "input": text}

        try:
            response = httpx.post(url, json=payload, timeout=self.embedding_timeout)
            response.raise_for_status()
            data = response.json()

            if self.embedding_type == "ollama":
                raw = data["embedding"]
            else:
                raw = data["data"][0]["embedding"]

            vec = np.array(raw, dtype="float32")
            return vec / np.linalg.norm(vec)   # L2-normalise for cosine sim

        except httpx.HTTPError as e:
            logger.error("HTTP error generating embedding: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error generating embedding: %s", e)
            raise

    # ── Vector store operations ────────────────────────────────────────────

    def _vec_literal(self, vec: np.ndarray) -> str:
        """Format a numpy vector as a pgvector literal string."""
        return "[" + ",".join(f"{v:.8f}" for v in vec.tolist()) + "]"

    def search_similar(
        self,
        query_embedding: np.ndarray,
        user_id: int,
        record_type: str = "chat_message",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return the top-k most similar embeddings for this user.

        Uses cosine distance (<=> operator) because all vectors are
        L2-normalised, making cosine and inner-product equivalent.
        """
        if user_id is None:
            logger.error("SECURITY VIOLATION: user_id is None in search_similar")
            raise ValueError("user_id is required for vector search")

        vec_str = self._vec_literal(query_embedding)

        rows = self.db.execute(
            text("""
                SELECT id, record_id, content, created_at,
                       1 - (embedding <=> CAST(:vec AS vector)) AS similarity
                FROM vector_embeddings
                WHERE user_id = :uid AND record_type = :rtype
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :k
            """),
            {"vec": vec_str, "uid": user_id, "rtype": record_type, "k": top_k},
        ).fetchall()

        results = []
        for row in rows:
            key_parts = str(row.record_id).split(":")
            session_id = key_parts[2] if len(key_parts) > 2 else None
            date_str   = key_parts[3] if len(key_parts) > 3 else None
            eval_score = float(key_parts[4].replace("eval_", "")) \
                if len(key_parts) > 4 and key_parts[4].startswith("eval_") else 0.0
            results.append({
                "id":         row.id,
                "text":       row.content,
                "similarity": float(row.similarity),
                "date":       date_str,
                "session_id": session_id,
                "eval_score": eval_score,
            })

        logger.debug("search_similar: %d results for user_id=%d", len(results), user_id)
        return results

    def persist_session(
        self,
        user_id: int,
        session_id: int,
        messages: List[ChatMessage],
        eval_score: Optional[float] = None,
    ) -> None:
        """Embed each message and store it in the vector table."""
        if user_id is None:
            logger.error("SECURITY VIOLATION: user_id is None in persist_session")
            raise ValueError("user_id is required for session persistence")

        if not messages:
            logger.debug("No messages to persist for session %d", session_id)
            return

        from datetime import datetime
        date_str  = datetime.now().strftime("%Y-%m-%d")
        score_str = f"eval_{eval_score:.1f}" if eval_score else "eval_0.0"
        key       = f"chat:{user_id}:{session_id}:{date_str}:{score_str}"

        persisted = 0
        for msg in messages:
            try:
                vec = self.generate_embedding(msg.content)
                row = VectorEmbedding(
                    user_id=user_id,
                    record_type="chat_message",
                    record_id=key,
                    content=msg.content,
                    embedding=vec.tolist(),
                )
                self.db.add(row)
                persisted += 1
            except Exception as e:
                logger.warning("Skipping message %s (embedding failed): %s", msg.id, e)

        try:
            self.db.commit()
            logger.info("Persisted %d/%d messages for session %d", persisted, len(messages), session_id)
        except Exception as e:
            logger.error("Error committing embeddings: %s", e)
            self.db.rollback()

    def delete_session(self, user_id: int, session_id: int) -> None:
        """Remove all embeddings for a session."""
        if user_id is None:
            logger.error("SECURITY VIOLATION: user_id is None in delete_session")
            raise ValueError("user_id is required for session deletion")

        try:
            prefix = f"chat:{user_id}:{session_id}:"
            deleted = (
                self.db.query(VectorEmbedding)
                .filter(
                    VectorEmbedding.user_id == user_id,
                    VectorEmbedding.record_type == "chat_message",
                    VectorEmbedding.record_id.like(f"{prefix}%"),
                )
                .delete(synchronize_session=False)
            )
            self.db.commit()
            logger.info("Deleted %d embeddings for session %d", deleted, session_id)
        except Exception as e:
            logger.error("Error deleting session %d: %s", session_id, e)
            self.db.rollback()
            raise

    # ── Two-layer context retrieval ────────────────────────────────────────

    def retrieve_context(
        self,
        query: str,
        user_id: int,
        active_session_messages: List[ChatMessage],
        top_k: int = 5,
    ) -> str:
        """
        Build context from both layers and return a formatted string.

        Layer 1 (always): last 10 messages of the current session.
        Layer 2 (best-effort): semantically similar past messages from pgvector.
        """
        if user_id is None:
            logger.error("SECURITY VIOLATION: user_id is None in retrieve_context")
            raise ValueError("user_id is required for context retrieval")

        start = time.time()
        parts: List[str] = []

        # Layer 1 — current session buffer
        if active_session_messages:
            parts.append("=== Current Session ===")
            for msg in active_session_messages[-10:]:
                parts.append(f"{msg.role}: {msg.content}")

        # Layer 2 — pgvector search
        t_vec = time.time()
        try:
            q_vec = self.generate_embedding(query)
            similar = self.search_similar(q_vec, user_id=user_id, top_k=top_k)

            vec_ms = (time.time() - t_vec) * 1000
            logger.debug("Vector retrieval: %dms for user_id=%d", vec_ms, user_id)
            if vec_ms > 500:
                logger.warning("Vector retrieval exceeded 500ms: %dms", vec_ms)

            if similar:
                parts.append("\n=== Relevant Past Conversations ===")
                for m in similar:
                    parts.append(f"[{m.get('date','?')}, score:{m.get('eval_score',0):.1f}] {m['text']}")

        except httpx.TimeoutException:
            logger.warning(
                "Embedding service timed out after %ds — continuing with session buffer only",
                self.embedding_timeout,
            )
        except Exception as e:
            logger.warning(
                "Vector store unavailable (%s) — continuing with session buffer only",
                type(e).__name__,
            )

        logger.debug("Context retrieval completed in %dms", (time.time() - start) * 1000)
        return "\n".join(parts)
