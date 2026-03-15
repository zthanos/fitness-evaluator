"""Chat Session Service

Handles session lifecycle and persistence management for chat conversations.

Responsibilities:
- Create/load/delete chat sessions
- Maintain active in-memory message buffer
- Load session messages from database
- Append user/assistant messages to buffer
- Persist session to database and vector store
- Clear buffer on session switch

Requirements: Phase 1 - Extract ChatSessionService
Design: ChatSessionService Interface (design.md)
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.services.rag_engine import RAGEngine

logger = logging.getLogger(__name__)


class ChatSessionService:
    """Session lifecycle and persistence management.

    This is the single source of truth for chat session state.  The handler
    reads conversation history from here and passes it to ``ChatAgent``; after
    the agent returns an ``AgentResult`` the handler calls
    ``append_messages()`` to persist the new turn.

    Owns:
        - Session creation / loading / deletion
        - Active in-memory message buffers (``active_buffers``)
        - Session persistence to database and vector store

    Does NOT own:
        - Context building logic  → ``ChatContextBuilder``
        - Message content generation → ``ChatAgent``
        - Tool execution → ``ToolOrchestrator``
        - LLM invocation → ``LLMAdapter``

    Contract with ChatAgent (see ``app.services.contracts``):
        - ``get_active_buffer()`` returns ``List[ChatMessage]`` which the
          handler converts to ``List[ConversationTurn]`` before passing to
          ``ChatAgent.execute()``.
        - ``append_messages()`` accepts the ``AgentResult.content`` string
          produced by the agent.

    See Also:
        ``app.services.contracts.ConversationTurn``
        ``app.services.contracts.AgentResult``
    """

    def __init__(self, db: Session, rag_engine: RAGEngine):
        """
        Initialize chat session service.

        Args:
            db: SQLAlchemy database session
            rag_engine: RAG engine for vector store operations
        """
        self.db = db
        self.rag_engine = rag_engine

        # Active buffers: session_id -> List[ChatMessage]
        self.active_buffers: Dict[int, List[ChatMessage]] = {}

        logger.info("ChatSessionService initialized")

    def create_session(self, athlete_id: int, title: str = "New Chat") -> int:
        """
        Create new chat session.

        Args:
            athlete_id: Athlete/user ID
            title: Session title

        Returns:
            session_id: ID of created session

        Requirements: 1.1 Session Lifecycle Extraction
        """
        try:
            # Create session record
            session = ChatSession(
                athlete_id=athlete_id,
                title=title,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            # Initialize empty buffer
            self.active_buffers[session.id] = []

            logger.info(
                f"Created session {session.id} for athlete {athlete_id}",
                extra={
                    "session_id": session.id,
                    "athlete_id": athlete_id,
                    "title": title
                }
            )

            return session.id

        except Exception as e:
            logger.error(
                f"Error creating session: {str(e)}",
                extra={"athlete_id": athlete_id},
                exc_info=True
            )
            self.db.rollback()
            raise

    def load_session(self, session_id: int) -> List[ChatMessage]:
        """
        Load session messages into active buffer.

        Args:
            session_id: Session ID to load

        Returns:
            List of ChatMessage objects ordered chronologically

        Requirements: 1.1 Session Lifecycle Extraction
        """
        try:
            # Query messages from database
            messages = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).all()

            # Load into active buffer
            self.active_buffers[session_id] = messages

            logger.info(
                f"Loaded {len(messages)} messages for session {session_id}",
                extra={
                    "session_id": session_id,
                    "message_count": len(messages)
                }
            )

            return messages

        except Exception as e:
            logger.error(
                f"Error loading session {session_id}: {str(e)}",
                extra={"session_id": session_id},
                exc_info=True
            )
            raise

    def get_active_buffer(self, session_id: int) -> List[ChatMessage]:
        """Get current active buffer for a session.

        The returned list is a *shallow copy* so callers cannot mutate the
        internal buffer.  The handler converts each ``ChatMessage`` to a
        ``ConversationTurn`` (via ``ConversationTurn.from_chat_message``)
        before forwarding to ``ChatAgent.execute()``.

        Args:
            session_id: Numeric session identifier.

        Returns:
            Chronologically ordered ``ChatMessage`` objects currently held
            in memory for *session_id*.  Returns an empty list when the
            session has not been loaded or has no messages.

        Example::

            history = session_service.get_active_buffer(42)
            turns = [ConversationTurn.from_chat_message(m) for m in history]

        Requirements: 1.2 Session State Isolation
        """
        # Return copy to prevent external modification
        return self.active_buffers.get(session_id, []).copy()

    def append_messages(
        self,
        session_id: int,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Append a user/assistant turn to the active buffer.

        Called by the handler after ``ChatAgent.execute()`` returns an
        ``AgentResult``.  The *assistant_message* is typically
        ``AgentResult.content``.

        .. note::
           This does **not** persist to the database.  Call
           ``persist_session()`` afterwards to flush.

        Args:
            session_id: Numeric session identifier.
            user_message: The athlete's original query text.
            assistant_message: The assistant response (``AgentResult.content``).

        Example::

            result: AgentResult = await agent.execute(...)
            session_service.append_messages(
                session_id=42,
                user_message="How was my long run?",
                assistant_message=result.content,
            )

        Requirements: 1.1 Session Lifecycle Extraction
        """
        try:
            # Ensure buffer exists
            if session_id not in self.active_buffers:
                self.active_buffers[session_id] = []

            # Create message objects (not persisted yet)
            user_msg = ChatMessage(
                session_id=session_id,
                role='user',
                content=user_message,
                created_at=datetime.utcnow()
            )

            assistant_msg = ChatMessage(
                session_id=session_id,
                role='assistant',
                content=assistant_message,
                created_at=datetime.utcnow()
            )

            # Add to active buffer
            self.active_buffers[session_id].append(user_msg)
            self.active_buffers[session_id].append(assistant_msg)

            logger.debug(
                f"Appended messages to session {session_id} buffer",
                extra={
                    "session_id": session_id,
                    "buffer_size": len(self.active_buffers[session_id])
                }
            )

        except Exception as e:
            logger.error(
                f"Error appending messages to session {session_id}: {str(e)}",
                extra={"session_id": session_id},
                exc_info=True
            )
            raise

    def persist_session(
        self,
        session_id: int,
        eval_score: Optional[float] = None
    ) -> None:
        """
        Persist session to database and vector store.

        Args:
            session_id: Session to persist
            eval_score: Optional quality score for the session

        Requirements: 1.1 Session Lifecycle Extraction
        """
        try:
            messages = self.active_buffers.get(session_id, [])

            if not messages:
                logger.info(
                    f"No messages to persist for session {session_id}",
                    extra={"session_id": session_id}
                )
                return

            # Get session to extract athlete_id
            session = self.db.query(ChatSession).filter(
                ChatSession.id == session_id
            ).first()

            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Persist messages to database
            for msg in messages:
                # Only add if not already in database
                if msg.id is None:
                    self.db.add(msg)

            # Update session timestamp
            session.updated_at = datetime.utcnow()

            self.db.commit()

            # Persist to vector store
            self.rag_engine.persist_session(
                user_id=session.athlete_id,
                session_id=session_id,
                messages=messages,
                eval_score=eval_score
            )

            logger.info(
                f"Persisted {len(messages)} messages for session {session_id}",
                extra={
                    "session_id": session_id,
                    "athlete_id": session.athlete_id,
                    "message_count": len(messages),
                    "eval_score": eval_score
                }
            )

        except Exception as e:
            logger.error(
                f"Error persisting session {session_id}: {str(e)}",
                extra={"session_id": session_id},
                exc_info=True
            )
            self.db.rollback()
            raise

    def clear_buffer(self, session_id: int) -> None:
        """
        Clear active buffer for session.

        Args:
            session_id: Session ID

        Requirements: 1.2 Session State Isolation
        """
        if session_id in self.active_buffers:
            self.active_buffers[session_id].clear()

            logger.debug(
                f"Cleared buffer for session {session_id}",
                extra={"session_id": session_id}
            )

    def delete_session(self, session_id: int) -> None:
        """
        Delete session from database and vector store.

        Removes all messages and embeddings.

        Args:
            session_id: Session ID to delete

        Requirements: 1.1 Session Lifecycle Extraction
        """
        try:
            # Get session to extract athlete_id
            session = self.db.query(ChatSession).filter(
                ChatSession.id == session_id
            ).first()

            if not session:
                logger.warning(
                    f"Session {session_id} not found for deletion",
                    extra={"session_id": session_id}
                )
                return

            athlete_id = session.athlete_id

            # Delete from vector store
            self.rag_engine.delete_session(
                user_id=athlete_id,
                session_id=session_id
            )

            # Delete from database (cascade will delete messages)
            self.db.delete(session)
            self.db.commit()

            # Clear active buffer
            if session_id in self.active_buffers:
                del self.active_buffers[session_id]

            logger.info(
                f"Deleted session {session_id}",
                extra={
                    "session_id": session_id,
                    "athlete_id": athlete_id
                }
            )

        except Exception as e:
            logger.error(
                f"Error deleting session {session_id}: {str(e)}",
                extra={"session_id": session_id},
                exc_info=True
            )
            self.db.rollback()
            raise
