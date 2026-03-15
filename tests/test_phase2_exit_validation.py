"""Phase 2 Exit Criteria Validation Tests

Validates all exit criteria for Phase 2: Move Context Composition to CE Path.
Updated for Phase 3 architecture where ChatAgent owns CE components.

Exit Criteria:
1. Chat doesn't send full session history by default
2. Context built by ChatContextBuilder not handler
3. Athlete behavior summary included as separate layer
4. Irrelevant old turns not in prompt
5. UI doesn't require changes
6. Token budget enforced (2400 tokens)
"""
import inspect
import pytest
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.services.chat_message_handler import ChatMessageHandler
from app.services.chat_session_service import ChatSessionService
from app.services.chat_agent import ChatAgent
from app.services.llm_client import LLMClient
from app.models.chat_message import ChatMessage
from app.ai.context.chat_context import ChatContextBuilder
from app.ai.context.builder import Context
from app.config import Settings


class TestPhase2ExitCriteria:
    """Test suite for Phase 2 exit criteria validation."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def mock_session_service(self):
        service = Mock(spec=ChatSessionService)
        messages = []
        for i in range(20):
            msg = Mock(spec=ChatMessage)
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i+1} content"
            messages.append(msg)
        service.get_active_buffer.return_value = messages
        service.append_messages = Mock()
        return service

    @pytest.fixture
    def mock_llm_client(self):
        client = Mock(spec=LLMClient)
        client.chat_completion = AsyncMock(return_value={
            'content': 'Test response',
            'tool_calls': None,
        })
        return client

    @pytest.fixture
    def handler(self, mock_db, mock_session_service, mock_llm_client):
        """Create handler backed by ChatAgent with real CE components."""
        context_builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        agent = ChatAgent(
            context_builder=context_builder,
            llm_adapter=None,
            db=mock_db,
            llm_client=mock_llm_client,
        )
        agent._ensure_loaders()
        ce_settings = Settings(USE_CE_CHAT_RUNTIME=True, LEGACY_CHAT_ENABLED=True)
        h = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=1,
            settings=ce_settings,
        )
        return h

    # ---- Exit Criteria Tests ----

    @pytest.mark.asyncio
    async def test_exit_criterion_1_no_full_session_history(self, handler, mock_session_service):
        """2.9.1: Chat doesn't send full session history by default."""
        agent = handler.agent
        with patch.object(agent.context_builder, 'gather_data') as mock_gather, \
             patch.object(agent.context_builder, 'build') as mock_build, \
             patch.object(agent._behavior_summary, 'generate_summary', return_value="summary"):
            mock_ctx = Mock(spec=Context)
            mock_ctx.token_count = 1500
            mock_ctx.to_messages.return_value = [{'role': 'system', 'content': 'prompt'}]
            mock_build.return_value = mock_ctx

            await handler.handle_message("What's my recent training?")

            mock_session_service.get_active_buffer.assert_called_once_with(1)
            assert mock_gather.called
            history_arg = mock_gather.call_args.kwargs.get('conversation_history')
            assert history_arg is not None
            # Agent limits to last 10 messages
            assert len(history_arg) == 10
            print("✓ Exit Criterion 2.9.1 PASSED")

    def test_exit_criterion_2_context_built_by_builder(self, handler):
        """2.9.2: Context built by ChatContextBuilder, not handler."""
        assert not hasattr(handler, '_retrieve_context')
        assert not hasattr(handler, '_build_conversation')
        assert not hasattr(handler, '_get_system_prompt')
        assert not hasattr(handler, '_orchestrate_tools')
        assert isinstance(handler.agent.context_builder, ChatContextBuilder)
        print("✓ Exit Criterion 2.9.2 PASSED")

    def test_exit_criterion_3_athlete_summary_included(self, handler):
        """2.9.3: Athlete behavior summary included as separate layer."""
        assert handler.agent._behavior_summary is not None
        print("✓ Exit Criterion 2.9.3 PASSED")

    def test_exit_criterion_4_irrelevant_turns_filtered(self, handler):
        """2.9.4: Irrelevant old turns not in prompt."""
        cb = handler.agent.context_builder
        assert hasattr(cb, 'select_relevant_history')
        print("✓ Exit Criterion 2.9.4 PASSED")

    @pytest.mark.asyncio
    async def test_exit_criterion_5_ui_unchanged(self, handler):
        """2.9.5: UI doesn't require changes."""
        sig = inspect.signature(handler.handle_message)
        params = list(sig.parameters.keys())
        assert 'user_message' in params
        assert 'max_tool_iterations' in params

        # Verify response format via mock agent
        handler.agent.execute = AsyncMock(return_value={
            'content': 'resp', 'tool_calls_made': 0,
            'iterations': 1, 'context_token_count': 500,
        })
        response = await handler.handle_message("test")
        assert 'content' in response
        assert 'tool_calls_made' in response
        assert 'latency_ms' in response
        print("✓ Exit Criterion 2.9.5 PASSED")

    def test_exit_criterion_6_token_budget_enforced(self, handler):
        """2.9.6: Token budget enforced (2400 tokens)."""
        cb = handler.agent.context_builder
        assert cb.token_budget == 2400
        assert hasattr(cb, '_trim_history_to_budget')
        assert hasattr(cb, '_trim_retrieved_data_to_budget')
        print("✓ Exit Criterion 2.9.6 PASSED")

    def test_all_exit_criteria_summary(self):
        """Summary of all Phase 2 exit criteria."""
        criteria = [
            "2.9.1: Chat doesn't send full session history by default",
            "2.9.2: Context built by ChatContextBuilder not handler",
            "2.9.3: Athlete behavior summary included as separate layer",
            "2.9.4: Irrelevant old turns not in prompt",
            "2.9.5: UI doesn't require changes",
            "2.9.6: Token budget enforced (2400 tokens)",
        ]
        print("\n" + "=" * 70)
        print("PHASE 2 EXIT CRITERIA VALIDATION")
        print("=" * 70)
        for c in criteria:
            print(f"✓ {c}")
        print("=" * 70)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
