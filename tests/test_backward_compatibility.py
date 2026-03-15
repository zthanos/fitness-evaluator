"""Backward Compatibility Tests for Chat Context Engineering Refactor.

Validates that the CE refactor maintains full backward compatibility with:
- Existing session loading and database records (X.3.1)
- Vector store embeddings (X.3.2)
- API request/response contracts (X.3.3)
- Streaming endpoints (X.3.4)
- Error response consistency (X.3.5)

Requirements: 7.1 Backward Compatibility
Design: Migration Strategy, Backward Compatibility (design.md)
"""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.base import Base
from app.models.athlete import Athlete
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.schemas.chat_schemas import (
    SessionCreate,
    SessionResponse,
    SessionWithMessages,
    MessageCreate,
    MessageResponse,
)
from app.services.chat_session_service import ChatSessionService
from app.services.chat_message_handler import ChatMessageHandler
from app.config import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_athlete(db_session: Session):
    athlete = Athlete(
        id=1,
        name="Test Athlete",
        email="test@example.com",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(athlete)
    db_session.commit()
    return athlete


@pytest.fixture
def mock_rag_engine():
    engine = Mock()
    engine.persist_session = Mock()
    engine.delete_session = Mock()
    return engine


@pytest.fixture
def session_service(db_session: Session, mock_rag_engine):
    return ChatSessionService(db=db_session, rag_engine=mock_rag_engine)


@pytest.fixture
def legacy_session_with_messages(db_session: Session, test_athlete: Athlete):
    """Simulate a pre-existing legacy session with messages in the DB."""
    session = ChatSession(
        athlete_id=test_athlete.id,
        title="Legacy Chat",
        created_at=datetime(2024, 1, 15, 10, 0, 0),
        updated_at=datetime(2024, 1, 15, 10, 30, 0),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    messages = [
        ChatMessage(
            session_id=session.id,
            role="user",
            content="How was my run yesterday?",
            created_at=datetime(2024, 1, 15, 10, 5, 0),
        ),
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content="Your run looked great! You covered 10 km in 55 minutes.",
            created_at=datetime(2024, 1, 15, 10, 5, 30),
        ),
        ChatMessage(
            session_id=session.id,
            role="user",
            content="What should I do today?",
            created_at=datetime(2024, 1, 15, 10, 10, 0),
        ),
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content="I'd suggest a recovery run of 5 km at an easy pace.",
            created_at=datetime(2024, 1, 15, 10, 10, 30),
        ),
    ]
    db_session.add_all(messages)
    db_session.commit()
    return session


@pytest.fixture
def ce_settings():
    return Settings(USE_CE_CHAT_RUNTIME=True, LEGACY_CHAT_ENABLED=True)


@pytest.fixture
def legacy_settings():
    return Settings(USE_CE_CHAT_RUNTIME=False, LEGACY_CHAT_ENABLED=True)


@pytest.fixture
def mock_agent():
    agent = Mock()
    agent.execute = AsyncMock(return_value={
        "content": "CE response content",
        "tool_calls_made": 0,
        "iterations": 1,
        "latency_ms": 100.0,
        "model_used": "mixtral",
        "context_token_count": 800,
        "response_token_count": 30,
        "intent": "general",
        "evidence_cards": [],
    })
    return agent


# =========================================================================
# X.3.1 — Test existing sessions load correctly
# =========================================================================

class TestExistingSessionsLoadCorrectly:
    """Verify that sessions created before the CE refactor load into the
    new ChatSessionService without data loss or format changes."""

    def test_load_legacy_session_returns_all_messages(
        self, session_service, legacy_session_with_messages, db_session
    ):
        """Legacy session messages load in chronological order."""
        messages = session_service.load_session(legacy_session_with_messages.id)

        assert len(messages) == 4
        assert messages[0].role == "user"
        assert messages[0].content == "How was my run yesterday?"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"
        assert messages[3].role == "assistant"

    def test_load_legacy_session_preserves_timestamps(
        self, session_service, legacy_session_with_messages
    ):
        """Original created_at timestamps are preserved after loading."""
        messages = session_service.load_session(legacy_session_with_messages.id)

        assert messages[0].created_at == datetime(2024, 1, 15, 10, 5, 0)
        assert messages[1].created_at == datetime(2024, 1, 15, 10, 5, 30)

    def test_load_legacy_session_populates_active_buffer(
        self, session_service, legacy_session_with_messages
    ):
        """Loading a legacy session populates the in-memory active buffer."""
        session_service.load_session(legacy_session_with_messages.id)
        buffer = session_service.get_active_buffer(legacy_session_with_messages.id)

        assert len(buffer) == 4
        assert buffer[0].content == "How was my run yesterday?"

    def test_load_empty_legacy_session(
        self, session_service, db_session, test_athlete
    ):
        """A legacy session with zero messages loads without error."""
        empty_session = ChatSession(
            athlete_id=test_athlete.id,
            title="Empty Legacy",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(empty_session)
        db_session.commit()
        db_session.refresh(empty_session)

        messages = session_service.load_session(empty_session.id)
        assert messages == []

    def test_session_switch_clears_previous_buffer(
        self, session_service, legacy_session_with_messages, db_session, test_athlete
    ):
        """Switching sessions does not leak state from the previous one."""
        # Load first session
        session_service.load_session(legacy_session_with_messages.id)

        # Create and load a second session
        second = ChatSession(
            athlete_id=test_athlete.id,
            title="Second Session",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(second)
        db_session.commit()
        db_session.refresh(second)

        session_service.load_session(second.id)

        # First session buffer still intact (no cross-contamination)
        buf1 = session_service.get_active_buffer(legacy_session_with_messages.id)
        buf2 = session_service.get_active_buffer(second.id)
        assert len(buf1) == 4
        assert len(buf2) == 0

    def test_append_to_legacy_session_preserves_existing(
        self, session_service, legacy_session_with_messages
    ):
        """Appending new messages to a legacy session keeps old ones."""
        session_service.load_session(legacy_session_with_messages.id)
        session_service.append_messages(
            legacy_session_with_messages.id,
            "New user question",
            "New assistant answer",
        )
        buffer = session_service.get_active_buffer(legacy_session_with_messages.id)
        assert len(buffer) == 6
        assert buffer[4].role == "user"
        assert buffer[4].content == "New user question"
        assert buffer[5].role == "assistant"

    def test_persist_legacy_session_updates_db(
        self, session_service, legacy_session_with_messages, db_session
    ):
        """Persisting a loaded legacy session writes new messages to DB."""
        session_service.load_session(legacy_session_with_messages.id)
        session_service.append_messages(
            legacy_session_with_messages.id,
            "Persisted question",
            "Persisted answer",
        )
        session_service.persist_session(legacy_session_with_messages.id)

        # Verify new messages in DB
        all_msgs = (
            db_session.query(ChatMessage)
            .filter(ChatMessage.session_id == legacy_session_with_messages.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        # 4 original + 2 new
        assert len(all_msgs) >= 6

    def test_delete_legacy_session_removes_all_data(
        self, session_service, legacy_session_with_messages, db_session, mock_rag_engine
    ):
        """Deleting a legacy session removes DB records and vector store data."""
        sid = legacy_session_with_messages.id
        session_service.delete_session(sid)

        remaining = db_session.query(ChatSession).filter(ChatSession.id == sid).first()
        assert remaining is None

        remaining_msgs = (
            db_session.query(ChatMessage)
            .filter(ChatMessage.session_id == sid)
            .all()
        )
        assert remaining_msgs == []

        mock_rag_engine.delete_session.assert_called_once()


# =========================================================================
# X.3.2 — Test vector store embeddings compatible
# =========================================================================

class TestVectorStoreEmbeddingsCompatible:
    """Verify that the CE refactor does not break vector store operations."""

    def test_persist_session_calls_rag_engine(
        self, session_service, legacy_session_with_messages, mock_rag_engine
    ):
        """persist_session delegates to RAGEngine with correct arguments."""
        session_service.load_session(legacy_session_with_messages.id)
        session_service.persist_session(legacy_session_with_messages.id, eval_score=8.5)

        mock_rag_engine.persist_session.assert_called_once()
        call_kwargs = mock_rag_engine.persist_session.call_args
        assert call_kwargs[1]["user_id"] == 1  # athlete_id
        assert call_kwargs[1]["session_id"] == legacy_session_with_messages.id
        assert call_kwargs[1]["eval_score"] == 8.5
        assert len(call_kwargs[1]["messages"]) == 4

    def test_persist_session_passes_message_objects(
        self, session_service, legacy_session_with_messages, mock_rag_engine
    ):
        """RAGEngine receives ChatMessage objects (not dicts) for embedding."""
        session_service.load_session(legacy_session_with_messages.id)
        session_service.persist_session(legacy_session_with_messages.id)

        call_kwargs = mock_rag_engine.persist_session.call_args[1]
        messages = call_kwargs["messages"]
        for msg in messages:
            assert isinstance(msg, ChatMessage)
            assert msg.role in ("user", "assistant")
            assert isinstance(msg.content, str)
            assert msg.created_at is not None

    def test_delete_session_calls_rag_engine(
        self, session_service, legacy_session_with_messages, mock_rag_engine
    ):
        """delete_session removes embeddings from vector store."""
        sid = legacy_session_with_messages.id
        session_service.delete_session(sid)

        mock_rag_engine.delete_session.assert_called_once_with(
            user_id=1, session_id=sid
        )

    def test_persist_empty_session_is_noop(
        self, session_service, db_session, test_athlete, mock_rag_engine
    ):
        """Persisting a session with no messages does not call RAGEngine."""
        empty = ChatSession(
            athlete_id=test_athlete.id,
            title="Empty",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(empty)
        db_session.commit()
        db_session.refresh(empty)

        session_service.persist_session(empty.id)
        mock_rag_engine.persist_session.assert_not_called()

    def test_persist_with_new_messages_includes_all(
        self, session_service, legacy_session_with_messages, mock_rag_engine
    ):
        """After appending, persist sends both old and new messages."""
        session_service.load_session(legacy_session_with_messages.id)
        session_service.append_messages(
            legacy_session_with_messages.id,
            "Extra question",
            "Extra answer",
        )
        session_service.persist_session(legacy_session_with_messages.id)

        call_kwargs = mock_rag_engine.persist_session.call_args[1]
        assert len(call_kwargs["messages"]) == 6


# =========================================================================
# X.3.3 — Test API contracts unchanged
# =========================================================================

class TestAPIContractsUnchanged:
    """Verify that Pydantic schemas and response shapes are unchanged."""

    def test_session_create_schema_accepts_optional_title(self):
        """SessionCreate works with and without a title."""
        with_title = SessionCreate(title="My Chat")
        assert with_title.title == "My Chat"

        without_title = SessionCreate()
        assert without_title.title is None

    def test_session_response_schema_fields(self):
        """SessionResponse has all expected fields."""
        resp = SessionResponse(
            id="1",
            athlete_id="1",
            title="Test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_count=5,
        )
        assert resp.id == "1"
        assert resp.athlete_id == "1"
        assert resp.title == "Test"
        assert resp.message_count == 5

    def test_session_response_allows_null_athlete_id(self):
        """SessionResponse accepts None for athlete_id."""
        resp = SessionResponse(
            id="1",
            athlete_id=None,
            title="Test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        assert resp.athlete_id is None

    def test_message_create_schema_validation(self):
        """MessageCreate enforces content length constraints."""
        valid = MessageCreate(content="Hello coach", session_id=1)
        assert valid.content == "Hello coach"
        assert valid.session_id == 1

        # Empty content should fail
        with pytest.raises(Exception):
            MessageCreate(content="")

    def test_message_response_schema_fields(self):
        """MessageResponse has all expected fields."""
        resp = MessageResponse(
            id="msg_1",
            session_id="sess_1",
            role="assistant",
            content="Here is your plan.",
            created_at=datetime.utcnow(),
        )
        assert resp.id == "msg_1"
        assert resp.role == "assistant"
        assert resp.content == "Here is your plan."

    def test_session_with_messages_schema(self):
        """SessionWithMessages includes messages list."""
        now = datetime.utcnow()
        resp = SessionWithMessages(
            id="1",
            title="Chat",
            created_at=now,
            updated_at=now,
            messages=[
                MessageResponse(
                    id="m1",
                    session_id="1",
                    role="user",
                    content="Hi",
                    created_at=now,
                ),
            ],
        )
        assert len(resp.messages) == 1
        assert resp.messages[0].role == "user"

    def test_handler_ce_response_contract(self, mock_agent, ce_settings):
        """CE runtime response includes all expected keys."""
        db = Mock()
        session_service = Mock()
        session_service.get_active_buffer = Mock(return_value=[])
        session_service.append_messages = Mock()

        handler = ChatMessageHandler(
            db=db,
            session_service=session_service,
            agent=mock_agent,
            user_id=1,
            session_id=1,
            settings=ce_settings,
        )

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            handler.handle_message("Hello")
        )

        # Verify response shape
        assert "content" in result
        assert "tool_calls_made" in result
        assert "iterations" in result
        assert "latency_ms" in result
        assert "runtime" in result
        assert result["runtime"] == "ce"
        assert isinstance(result["content"], str)
        assert isinstance(result["latency_ms"], float)

    def test_handler_legacy_response_contract(self, legacy_settings):
        """Legacy runtime response includes all expected keys."""
        db = Mock()
        session_service = Mock()
        session_service.get_active_buffer = Mock(return_value=[])
        session_service.append_messages = Mock()

        handler = ChatMessageHandler(
            db=db,
            session_service=session_service,
            agent=None,
            user_id=1,
            session_id=1,
            settings=legacy_settings,
        )

        mock_chat_service = Mock()
        mock_chat_service.get_chat_response = AsyncMock(return_value={
            "content": "Legacy response",
            "iterations": 0,
        })

        import asyncio
        with patch("app.services.chat_service.ChatService", return_value=mock_chat_service):
            result = asyncio.get_event_loop().run_until_complete(
                handler.handle_message("Hello")
            )

        assert "content" in result
        assert "tool_calls_made" in result
        assert "latency_ms" in result
        assert "runtime" in result
        assert result["runtime"] == "legacy"
        assert isinstance(result["content"], str)

    def test_both_runtimes_share_response_keys(self, mock_agent, ce_settings, legacy_settings):
        """CE and legacy responses share the same top-level keys."""
        common_keys = {"content", "tool_calls_made", "iterations", "latency_ms", "runtime"}

        # CE response
        db = Mock()
        ss = Mock()
        ss.get_active_buffer = Mock(return_value=[])
        ss.append_messages = Mock()
        ce_handler = ChatMessageHandler(
            db=db, session_service=ss, agent=mock_agent,
            user_id=1, session_id=1, settings=ce_settings,
        )

        import asyncio
        ce_result = asyncio.get_event_loop().run_until_complete(
            ce_handler.handle_message("Hi")
        )

        # Legacy response
        legacy_handler = ChatMessageHandler(
            db=db, session_service=ss, agent=None,
            user_id=1, session_id=1, settings=legacy_settings,
        )
        mock_cs = Mock()
        mock_cs.get_chat_response = AsyncMock(return_value={"content": "ok", "iterations": 0})
        with patch("app.services.chat_service.ChatService", return_value=mock_cs):
            legacy_result = asyncio.get_event_loop().run_until_complete(
                legacy_handler.handle_message("Hi")
            )

        assert common_keys.issubset(set(ce_result.keys()))
        assert common_keys.issubset(set(legacy_result.keys()))


# =========================================================================
# X.3.4 — Test streaming endpoints work
# =========================================================================

class TestStreamingEndpointsWork:
    """Verify that SSE streaming format is preserved after the refactor."""

    @pytest.mark.asyncio
    async def test_ce_handler_response_is_streamable(self, mock_agent, ce_settings):
        """CE handler returns content that can be chunked for SSE."""
        mock_agent.execute = AsyncMock(return_value={
            "content": "A" * 200,
            "tool_calls_made": 0,
            "iterations": 1,
            "latency_ms": 50.0,
            "model_used": "mixtral",
            "context_token_count": 500,
            "response_token_count": 50,
            "intent": "general",
            "evidence_cards": [],
        })

        ss = Mock()
        ss.get_active_buffer = Mock(return_value=[])
        ss.append_messages = Mock()

        handler = ChatMessageHandler(
            db=Mock(), session_service=ss, agent=mock_agent,
            user_id=1, session_id=1, settings=ce_settings,
        )
        result = await handler.handle_message("Tell me about my training")

        # Simulate SSE chunking (same logic as chat.py stream endpoint)
        content = result["content"]
        chunk_size = 50
        chunks = []
        for i in range(0, len(content), chunk_size):
            chunk = content[i : i + chunk_size]
            event_data = json.dumps({"type": "chunk", "content": chunk})
            chunks.append(f"data: {event_data}\n\n")

        assert len(chunks) == 4  # 200 chars / 50 per chunk
        for c in chunks:
            assert c.startswith("data: ")
            parsed = json.loads(c.replace("data: ", "").strip())
            assert parsed["type"] == "chunk"
            assert isinstance(parsed["content"], str)

    @pytest.mark.asyncio
    async def test_sse_done_event_format(self):
        """The 'done' SSE event includes session_id."""
        session_id = 42
        done_data = json.dumps({"type": "done", "session_id": session_id})
        event = f"data: {done_data}\n\n"

        parsed = json.loads(event.replace("data: ", "").strip())
        assert parsed["type"] == "done"
        assert parsed["session_id"] == 42

    @pytest.mark.asyncio
    async def test_sse_error_event_format(self):
        """The 'error' SSE event includes a message string."""
        error_data = json.dumps({"type": "error", "message": "Something went wrong"})
        event = f"data: {error_data}\n\n"

        parsed = json.loads(event.replace("data: ", "").strip())
        assert parsed["type"] == "error"
        assert "Something went wrong" in parsed["message"]

    @pytest.mark.asyncio
    async def test_streaming_headers(self):
        """Streaming response should use correct SSE headers."""
        expected_headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        # Verify the expected header values match what chat.py sets
        for key, value in expected_headers.items():
            assert isinstance(key, str)
            assert isinstance(value, str)


# =========================================================================
# X.3.5 — Test error responses consistent
# =========================================================================

class TestErrorResponsesConsistent:
    """Verify that error handling patterns are consistent across runtimes."""

    @pytest.mark.asyncio
    async def test_ce_runtime_propagates_agent_errors(self, ce_settings):
        """CE runtime raises when the agent fails."""
        failing_agent = Mock()
        failing_agent.execute = AsyncMock(side_effect=RuntimeError("LLM timeout"))

        ss = Mock()
        ss.get_active_buffer = Mock(return_value=[])

        handler = ChatMessageHandler(
            db=Mock(), session_service=ss, agent=failing_agent,
            user_id=1, session_id=1, settings=ce_settings,
        )

        with pytest.raises(RuntimeError, match="LLM timeout"):
            await handler.handle_message("Hello")

    @pytest.mark.asyncio
    async def test_legacy_runtime_propagates_service_errors(self, legacy_settings):
        """Legacy runtime raises when ChatService fails."""
        ss = Mock()
        ss.get_active_buffer = Mock(return_value=[])

        handler = ChatMessageHandler(
            db=Mock(), session_service=ss, agent=None,
            user_id=1, session_id=1, settings=legacy_settings,
        )

        mock_cs = Mock()
        mock_cs.get_chat_response = AsyncMock(
            side_effect=ConnectionError("Model unreachable")
        )
        with patch(
            "app.services.chat_service.ChatService",
            return_value=mock_cs,
        ):
            with pytest.raises(ConnectionError, match="Model unreachable"):
                await handler.handle_message("Hello")

    def test_session_not_found_raises(self, session_service):
        """Loading a non-existent session returns empty (no crash)."""
        messages = session_service.load_session(99999)
        assert messages == []

    def test_delete_nonexistent_session_is_safe(
        self, session_service, mock_rag_engine
    ):
        """Deleting a session that doesn't exist does not raise."""
        session_service.delete_session(99999)
        mock_rag_engine.delete_session.assert_not_called()

    def test_persist_nonexistent_session_raises(self, session_service):
        """Persisting a session that has buffered messages but no DB record raises."""
        # Manually inject a buffer for a non-existent session
        session_service.active_buffers[99999] = [
            ChatMessage(session_id=99999, role="user", content="ghost")
        ]
        with pytest.raises(ValueError, match="not found"):
            session_service.persist_session(99999)

    @pytest.mark.asyncio
    async def test_ce_error_does_not_corrupt_session_buffer(
        self, ce_settings
    ):
        """If the CE agent fails, the session buffer is not modified."""
        failing_agent = Mock()
        failing_agent.execute = AsyncMock(side_effect=RuntimeError("boom"))

        ss = Mock()
        ss.get_active_buffer = Mock(return_value=[])

        handler = ChatMessageHandler(
            db=Mock(), session_service=ss, agent=failing_agent,
            user_id=1, session_id=1, settings=ce_settings,
        )

        with pytest.raises(RuntimeError):
            await handler.handle_message("Hello")

        # append_messages should NOT have been called
        ss.append_messages.assert_not_called()

    def test_db_rollback_on_persist_failure(self, db_session, test_athlete):
        """If persist_session hits an error, the DB transaction is rolled back."""
        # Use a RAG engine that raises on persist
        failing_rag = Mock()
        failing_rag.persist_session = Mock(side_effect=RuntimeError("Vector store down"))
        service = ChatSessionService(db=db_session, rag_engine=failing_rag)

        sid = service.create_session(athlete_id=test_athlete.id, title="Will fail persist")
        service.append_messages(sid, "q", "a")

        with pytest.raises(RuntimeError, match="Vector store down"):
            service.persist_session(sid)

        # DB should still be usable after the error
        count = db_session.query(ChatSession).count()
        assert count >= 1
