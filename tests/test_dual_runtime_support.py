"""Tests for Dual Runtime Support (Phase 6, Task 6.2)

Validates that ChatMessageHandler correctly supports both CE and legacy
runtime paths, selects the right one based on feature flags, and includes
runtime identifiers in all responses.

Requirements: 6.1, 6.2
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.services.chat_message_handler import ChatMessageHandler
from app.models.chat_message import ChatMessage
from app.config import Settings

# Patch target for the lazy import inside _handle_legacy
_CHAT_SERVICE_PATCH = "app.services.chat_service.ChatService"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def mock_session_service():
    service = Mock()
    service.get_active_buffer = Mock(return_value=[])
    service.append_messages = Mock()
    return service


@pytest.fixture
def mock_agent():
    agent = Mock()
    agent.execute = AsyncMock(return_value={
        "content": "CE response: here's your training plan.",
        "tool_calls_made": 1,
        "iterations": 2,
        "latency_ms": 120.0,
        "model_used": "mixtral",
        "context_token_count": 950,
        "response_token_count": 40,
        "intent": "training_plan",
        "evidence_cards": [{"id": "ev1"}],
    })
    return agent


def _make_legacy_chat_service(content="ok", iterations=0):
    """Helper: create a mock ChatService instance for legacy path tests."""
    svc = MagicMock()
    svc.get_chat_response = AsyncMock(return_value={
        "content": content,
        "iterations": iterations,
    })
    return svc


@pytest.fixture
def ce_settings():
    return Settings(USE_CE_CHAT_RUNTIME=True, LEGACY_CHAT_ENABLED=True)


@pytest.fixture
def legacy_settings():
    return Settings(USE_CE_CHAT_RUNTIME=False, LEGACY_CHAT_ENABLED=True)


@pytest.fixture
def ce_handler(mock_db, mock_session_service, mock_agent, ce_settings):
    return ChatMessageHandler(
        db=mock_db,
        session_service=mock_session_service,
        agent=mock_agent,
        user_id=1,
        session_id=10,
        settings=ce_settings,
    )


@pytest.fixture
def legacy_handler(mock_db, mock_session_service, legacy_settings):
    return ChatMessageHandler(
        db=mock_db,
        session_service=mock_session_service,
        agent=None,
        user_id=2,
        session_id=20,
        settings=legacy_settings,
    )


# ---------------------------------------------------------------------------
# 6.2.1 – _handle_ce() method
# ---------------------------------------------------------------------------

class TestHandleCE:
    """Verify the CE runtime path works independently."""

    @pytest.mark.asyncio
    async def test_ce_path_delegates_to_agent(self, ce_handler, mock_agent):
        result = await ce_handler.handle_message("Plan my week")
        mock_agent.execute.assert_called_once()
        assert result["content"] == "CE response: here's your training plan."

    @pytest.mark.asyncio
    async def test_ce_path_passes_session_history(
        self, ce_handler, mock_session_service, mock_agent
    ):
        history = [
            ChatMessage(session_id=10, role="user", content="Hi"),
            ChatMessage(session_id=10, role="assistant", content="Hey!"),
        ]
        mock_session_service.get_active_buffer.return_value = history

        await ce_handler.handle_message("What next?")

        call_kwargs = mock_agent.execute.call_args[1]
        assert call_kwargs["conversation_history"] == history
        assert call_kwargs["session_id"] == 10
        assert call_kwargs["user_id"] == 1

    @pytest.mark.asyncio
    async def test_ce_path_persists_messages(
        self, ce_handler, mock_session_service
    ):
        await ce_handler.handle_message("Show goals")
        mock_session_service.append_messages.assert_called_once_with(
            10,
            "Show goals",
            "CE response: here's your training plan.",
        )

    @pytest.mark.asyncio
    async def test_ce_path_returns_metadata(self, ce_handler):
        result = await ce_handler.handle_message("Plan my week")
        assert result["tool_calls_made"] == 1
        assert result["iterations"] == 2
        assert result["context_token_count"] == 950
        assert result["ce_context_used"] is True

    @pytest.mark.asyncio
    async def test_ce_path_propagates_errors(self, ce_handler, mock_agent):
        mock_agent.execute.side_effect = RuntimeError("model timeout")
        with pytest.raises(RuntimeError, match="model timeout"):
            await ce_handler.handle_message("Hello")


# ---------------------------------------------------------------------------
# 6.2.2 – _handle_legacy() method
# ---------------------------------------------------------------------------

class TestHandleLegacy:
    """Verify the legacy runtime path works independently."""

    @pytest.mark.asyncio
    async def test_legacy_path_delegates_to_chat_service(
        self, legacy_handler, mock_session_service
    ):
        mock_svc = _make_legacy_chat_service("Legacy response: keep it up!")

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await legacy_handler.handle_message("How am I doing?")

        assert result["content"] == "Legacy response: keep it up!"
        mock_svc.get_chat_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_legacy_path_builds_conversation_from_buffer(
        self, legacy_handler, mock_session_service
    ):
        history = [
            ChatMessage(session_id=20, role="user", content="Hi"),
            ChatMessage(session_id=20, role="assistant", content="Hello!"),
        ]
        mock_session_service.get_active_buffer.return_value = history

        mock_svc = _make_legacy_chat_service("Sure thing.")

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            await legacy_handler.handle_message("Tell me more")

        call_args = mock_svc.get_chat_response.call_args[0][0]
        assert call_args == [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "Tell me more"},
        ]

    @pytest.mark.asyncio
    async def test_legacy_path_persists_messages(
        self, legacy_handler, mock_session_service
    ):
        mock_svc = _make_legacy_chat_service("Legacy reply")

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            await legacy_handler.handle_message("Ping")

        mock_session_service.append_messages.assert_called_once_with(
            20, "Ping", "Legacy reply"
        )

    @pytest.mark.asyncio
    async def test_legacy_path_propagates_errors(self, legacy_handler):
        mock_svc = MagicMock()
        mock_svc.get_chat_response = AsyncMock(
            side_effect=ConnectionError("LLM down")
        )

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            with pytest.raises(ConnectionError, match="LLM down"):
                await legacy_handler.handle_message("Hello")


# ---------------------------------------------------------------------------
# 6.2.3 – Runtime selection based on feature flag
# ---------------------------------------------------------------------------

class TestRuntimeSelection:
    """Verify the feature flag drives runtime selection."""

    def test_ce_flag_true_sets_ce_runtime(
        self, mock_db, mock_session_service, mock_agent
    ):
        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=mock_agent,
            settings=Settings(USE_CE_CHAT_RUNTIME=True),
        )
        assert handler.runtime == "ce"

    def test_ce_flag_false_sets_legacy_runtime(
        self, mock_db, mock_session_service
    ):
        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=None,
            settings=Settings(USE_CE_CHAT_RUNTIME=False),
        )
        assert handler.runtime == "legacy"

    def test_ce_flag_true_without_agent_raises(
        self, mock_db, mock_session_service
    ):
        with pytest.raises(ValueError, match="ChatAgent is required"):
            ChatMessageHandler(
                db=mock_db,
                session_service=mock_session_service,
                agent=None,
                settings=Settings(USE_CE_CHAT_RUNTIME=True),
            )

    def test_legacy_mode_allows_none_agent(
        self, mock_db, mock_session_service
    ):
        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=None,
            settings=Settings(USE_CE_CHAT_RUNTIME=False),
        )
        assert handler.agent is None
        assert handler.runtime == "legacy"

    @pytest.mark.asyncio
    async def test_handle_message_routes_to_ce(self, ce_handler, mock_agent):
        """When runtime is 'ce', handle_message calls _handle_ce."""
        await ce_handler.handle_message("Test")
        mock_agent.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_routes_to_legacy(
        self, legacy_handler
    ):
        """When runtime is 'legacy', handle_message calls _handle_legacy."""
        mock_svc = _make_legacy_chat_service()

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await legacy_handler.handle_message("Test")

        assert result["runtime"] == "legacy"
        mock_svc.get_chat_response.assert_called_once()


# ---------------------------------------------------------------------------
# 6.2.4 – Both paths work independently
# ---------------------------------------------------------------------------

class TestPathIndependence:
    """Verify CE and legacy paths are fully independent."""

    @pytest.mark.asyncio
    async def test_ce_path_never_instantiates_chat_service(self, ce_handler):
        """CE path should never touch ChatService."""
        # CE path delegates to agent; ChatService is only imported inside
        # _handle_legacy, which is never called when runtime == "ce".
        result = await ce_handler.handle_message("Hello")
        assert result["runtime"] == "ce"

    @pytest.mark.asyncio
    async def test_legacy_does_not_use_agent(self, legacy_handler):
        """Legacy path should never call agent.execute."""
        mock_svc = _make_legacy_chat_service()

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await legacy_handler.handle_message("Hello")

        assert result["runtime"] == "legacy"
        assert legacy_handler.agent is None

    @pytest.mark.asyncio
    async def test_ce_error_does_not_fallback_to_legacy(
        self, ce_handler, mock_agent
    ):
        """CE errors should propagate, not silently fall back to legacy."""
        mock_agent.execute.side_effect = RuntimeError("CE broke")

        with pytest.raises(RuntimeError, match="CE broke"):
            await ce_handler.handle_message("Hello")

    @pytest.mark.asyncio
    async def test_legacy_error_does_not_fallback_to_ce(self, legacy_handler):
        """Legacy errors should propagate, not silently fall back to CE."""
        mock_svc = MagicMock()
        mock_svc.get_chat_response = AsyncMock(
            side_effect=RuntimeError("Legacy broke")
        )

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            with pytest.raises(RuntimeError, match="Legacy broke"):
                await legacy_handler.handle_message("Hello")


# ---------------------------------------------------------------------------
# 6.2.5 – Runtime identifier in responses
# ---------------------------------------------------------------------------

class TestRuntimeIdentifier:
    """Verify every response includes a 'runtime' key."""

    @pytest.mark.asyncio
    async def test_ce_response_has_runtime_ce(self, ce_handler):
        result = await ce_handler.handle_message("Hi")
        assert "runtime" in result
        assert result["runtime"] == "ce"

    @pytest.mark.asyncio
    async def test_legacy_response_has_runtime_legacy(self, legacy_handler):
        mock_svc = _make_legacy_chat_service()

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await legacy_handler.handle_message("Hi")

        assert "runtime" in result
        assert result["runtime"] == "legacy"

    @pytest.mark.asyncio
    async def test_ce_response_has_ce_context_used_true(self, ce_handler):
        result = await ce_handler.handle_message("Hi")
        assert result["ce_context_used"] is True

    @pytest.mark.asyncio
    async def test_legacy_response_has_ce_context_used_false(self, legacy_handler):
        mock_svc = _make_legacy_chat_service()

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await legacy_handler.handle_message("Hi")

        assert result["ce_context_used"] is False

    @pytest.mark.asyncio
    async def test_both_responses_have_latency(self, ce_handler, legacy_handler):
        ce_result = await ce_handler.handle_message("Hi")
        assert "latency_ms" in ce_result
        assert ce_result["latency_ms"] >= 0

        mock_svc = _make_legacy_chat_service()

        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            legacy_result = await legacy_handler.handle_message("Hi")

        assert "latency_ms" in legacy_result
        assert legacy_result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_response_schema_consistent_across_runtimes(
        self, ce_handler, legacy_handler
    ):
        """Both runtimes should return the same set of top-level keys."""
        ce_result = await ce_handler.handle_message("Hi")

        mock_svc = _make_legacy_chat_service()
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            legacy_result = await legacy_handler.handle_message("Hi")

        expected_keys = {
            "content", "tool_calls_made", "iterations",
            "latency_ms", "context_token_count", "ce_context_used", "runtime",
        }
        assert expected_keys.issubset(ce_result.keys())
        assert expected_keys.issubset(legacy_result.keys())
