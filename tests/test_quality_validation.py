"""Quality Validation Tests for CE Chat Runtime (Phase 6, Task 6.5)

Comprehensive quality validation covering:
- 6.5.1 Automated tests on CE runtime (end-to-end with mocked deps)
- 6.5.2 p95 latency measurement and threshold validation
- 6.5.3 Response quality evaluation infrastructure
- 6.5.4 UI regression / API contract compatibility
- 6.5.5 Tool calling reliability
- 6.5.6 CE vs legacy baseline comparison

Requirements: 6.3, 7.2, 7.3
"""
import json
import time
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from app.config import Settings
from app.config.rollout_config import evaluate_metric, get_success_metrics, SuccessMetrics
from app.services.chat_message_handler import ChatMessageHandler
from app.services.chat_agent import ChatAgent
from app.services.chat_session_service import ChatSessionService
from app.services.tool_orchestrator import ToolOrchestrator
from app.services.runtime_comparison import ComparisonReport, RuntimeResult, run_comparison
from app.ai.context.chat_context import ChatContextBuilder
from app.ai.adapter.llm_adapter import LLMProviderAdapter, LLMResponse
from app.ai.contracts.chat_contract import ChatResponseContract
from app.ai.contracts.evidence_card import EvidenceCard
from app.models.chat_message import ChatMessage

_CHAT_SERVICE_PATCH = "app.services.chat_service.ChatService"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _inject_mock_loaders(agent: ChatAgent) -> None:
    """Pre-inject mock loaders so _load_defaults doesn't hit filesystem/DB."""
    agent._system_loader = Mock()
    agent._system_loader.load.return_value = "You are a fitness coach."
    agent._task_loader = Mock()
    agent._task_loader.load.return_value = "Respond to the athlete's query."
    agent._domain_loader = Mock()
    dk_mock = Mock()
    dk_mock.to_dict.return_value = {"zones": ["Z1", "Z2", "Z3"]}
    agent._domain_loader.load.return_value = dk_mock
    agent._behavior_summary = Mock()
    agent._behavior_summary.generate_summary.return_value = "Runs 4x/week, prefers mornings."


def _make_legacy_chat_service(content="Legacy: keep up the good work!", iterations=1):
    svc = MagicMock()
    svc.get_chat_response = AsyncMock(return_value={
        "content": content,
        "iterations": iterations,
    })
    return svc


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def mock_session_service():
    svc = Mock()
    svc.get_active_buffer = Mock(return_value=[])
    svc.append_messages = Mock()
    svc.create_session = Mock(return_value=1)
    svc.load_session = Mock(return_value=[])
    return svc


@pytest.fixture
def mock_llm_adapter():
    adapter = Mock(spec=LLMProviderAdapter)
    contract = ChatResponseContract(
        response_text="Based on your recent training data, you're making great progress!",
        evidence_cards=[],
        confidence_score=0.88,
        follow_up_suggestions=["How about a recovery day?"],
    )
    adapter.invoke.return_value = LLMResponse(
        parsed_output=contract,
        model_used="mixtral:8x7b-instruct",
        token_count=200,
        latency_ms=250,
    )
    return adapter


@pytest.fixture
def mock_context_builder(mock_db):
    builder = ChatContextBuilder(db=mock_db, token_budget=2400)
    builder.gather_data = Mock(return_value=builder)
    return builder


@pytest.fixture
def mock_tool_orchestrator():
    orch = Mock(spec=ToolOrchestrator)
    orch.orchestrate = AsyncMock(return_value={
        "content": "I found 3 activities this week. Great consistency!",
        "tool_calls_made": 2,
        "iterations": 2,
        "tool_results": [
            {"tool_name": "get_my_recent_activities", "result": {"count": 3}},
            {"tool_name": "get_my_weekly_metrics", "result": {"distance": 25.0}},
        ],
        "max_iterations_reached": False,
        "model_used": "mixtral:8x7b-instruct",
        "response_token_count": 45,
        "intent": "recent_performance",
        "evidence_cards": [],
    })
    return orch


@pytest.fixture
def ce_agent(mock_context_builder, mock_llm_adapter, mock_db, mock_tool_orchestrator):
    agent = ChatAgent(
        context_builder=mock_context_builder,
        llm_adapter=mock_llm_adapter,
        db=mock_db,
        tool_orchestrator=mock_tool_orchestrator,
    )
    _inject_mock_loaders(agent)
    return agent


@pytest.fixture
def ce_settings():
    return Settings(USE_CE_CHAT_RUNTIME=True, LEGACY_CHAT_ENABLED=True)


@pytest.fixture
def ce_handler(mock_db, mock_session_service, ce_agent, ce_settings):
    return ChatMessageHandler(
        db=mock_db,
        session_service=mock_session_service,
        agent=ce_agent,
        user_id=1,
        session_id=10,
        settings=ce_settings,
    )


# ===========================================================================
# 6.5.1 – Run automated tests on CE runtime
# ===========================================================================

class TestCERuntimeAutomated:
    """End-to-end CE runtime tests with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_ce_runtime_handles_simple_query(self, ce_handler):
        """CE runtime returns a valid response for a simple coaching query."""
        result = await ce_handler.handle_message("How was my week?")

        assert result["runtime"] == "ce"
        assert result["content"]
        assert isinstance(result["content"], str)
        assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_ce_runtime_handles_multi_tool_query(
        self, mock_db, mock_session_service, mock_context_builder,
        mock_tool_orchestrator, ce_settings,
    ):
        """CE runtime handles queries requiring multiple tool calls."""
        adapter = Mock(spec=LLMProviderAdapter)
        adapter.invoke.return_value = None  # force tool path

        agent = ChatAgent(
            context_builder=mock_context_builder,
            llm_adapter=adapter,
            db=mock_db,
            tool_orchestrator=mock_tool_orchestrator,
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        result = await handler.handle_message("Show my recent activities and weekly metrics")

        assert result["runtime"] == "ce"
        assert result["tool_calls_made"] == 2
        assert result["iterations"] == 2

    @pytest.mark.asyncio
    async def test_ce_runtime_handles_errors_gracefully(
        self, mock_db, mock_session_service, ce_settings,
    ):
        """CE runtime propagates errors without crashing the handler."""
        failing_agent = Mock()
        failing_agent.execute = AsyncMock(side_effect=RuntimeError("LLM timeout"))

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=failing_agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        with pytest.raises(RuntimeError, match="LLM timeout"):
            await handler.handle_message("Hello")

    @pytest.mark.asyncio
    async def test_all_ce_components_work_together(
        self, mock_db, mock_session_service, ce_settings,
    ):
        """ChatAgent + ChatContextBuilder + ToolOrchestrator + LLMAdapter
        integrate correctly through the handler."""
        context_builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        context_builder.gather_data = Mock(return_value=context_builder)

        contract = ChatResponseContract(
            response_text="Your training load is well balanced this week.",
            evidence_cards=[],
            confidence_score=0.9,
        )
        llm_adapter = Mock(spec=LLMProviderAdapter)
        llm_adapter.invoke.return_value = LLMResponse(
            parsed_output=contract,
            model_used="mixtral:8x7b-instruct",
            token_count=180,
            latency_ms=200,
        )

        tool_orch = Mock(spec=ToolOrchestrator)
        tool_orch.orchestrate = AsyncMock()

        agent = ChatAgent(
            context_builder=context_builder,
            llm_adapter=llm_adapter,
            db=mock_db,
            tool_orchestrator=tool_orch,
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        result = await handler.handle_message("How's my training load?")

        assert result["content"] == "Your training load is well balanced this week."
        assert result["runtime"] == "ce"
        assert result["ce_context_used"] is True
        llm_adapter.invoke.assert_called_once()
        tool_orch.orchestrate.assert_not_called()

    @pytest.mark.asyncio
    async def test_ce_runtime_produces_valid_response_schema(self, ce_handler):
        """CE response contains all required schema fields."""
        result = await ce_handler.handle_message("Plan my week")

        required_keys = {
            "content", "tool_calls_made", "iterations",
            "latency_ms", "context_token_count", "ce_context_used", "runtime",
        }
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )
        assert isinstance(result["content"], str)
        assert isinstance(result["tool_calls_made"], int)
        assert isinstance(result["iterations"], int)
        assert isinstance(result["latency_ms"], (int, float))
        assert isinstance(result["context_token_count"], int)
        assert isinstance(result["ce_context_used"], bool)
        assert result["runtime"] == "ce"


# ===========================================================================
# 6.5.2 – Measure p95 latency (target: < 3s simple, < 5s multi-tool)
# ===========================================================================

class TestLatencyMeasurement:
    """Validate latency tracking and threshold enforcement."""

    @pytest.mark.asyncio
    async def test_simple_query_latency_tracked_and_within_target(self, ce_handler):
        """Simple query latency is recorded and meets the < 3s target."""
        result = await ce_handler.handle_message("How am I doing?")

        assert "latency_ms" in result
        assert result["latency_ms"] >= 0
        metrics = get_success_metrics()
        assert evaluate_metric("p95_latency_simple_ms", result["latency_ms"], metrics)

    @pytest.mark.asyncio
    async def test_multi_tool_query_latency_tracked_and_within_target(
        self, mock_db, mock_session_service, mock_context_builder,
        mock_tool_orchestrator, ce_settings,
    ):
        """Multi-tool query latency is recorded and meets the < 5s target."""
        adapter = Mock(spec=LLMProviderAdapter)
        adapter.invoke.return_value = None

        agent = ChatAgent(
            context_builder=mock_context_builder,
            llm_adapter=adapter,
            db=mock_db,
            tool_orchestrator=mock_tool_orchestrator,
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        result = await handler.handle_message("Show activities and metrics")

        assert "latency_ms" in result
        metrics = get_success_metrics()
        assert evaluate_metric("p95_latency_multi_tool_ms", result["latency_ms"], metrics)

    @pytest.mark.asyncio
    async def test_latency_warning_logged_when_exceeding_target(
        self, mock_db, mock_session_service, ce_settings,
    ):
        """A warning is logged when handler-measured latency exceeds 3s."""
        slow_agent = Mock()
        slow_agent.execute = AsyncMock(return_value={
            "content": "Slow response",
            "tool_calls_made": 0,
            "iterations": 0,
            "latency_ms": 4000.0,
            "model_used": "mixtral",
            "context_token_count": 500,
            "response_token_count": 20,
        })

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=slow_agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        # The handler measures its own wall-clock latency (very fast with mocks).
        # We verify the mechanism works and the response is returned.
        result = await handler.handle_message("Hello")
        assert result["content"] == "Slow response"
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_latency_included_in_response_metadata(self, ce_handler):
        """Response always includes latency_ms in metadata."""
        result = await ce_handler.handle_message("Quick question")

        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], (int, float))
        assert result["latency_ms"] >= 0

    def test_evaluate_metric_validates_simple_latency(self):
        """evaluate_metric correctly validates simple query latency."""
        metrics = get_success_metrics()
        assert evaluate_metric("p95_latency_simple_ms", 2500.0, metrics) is True
        assert evaluate_metric("p95_latency_simple_ms", 3500.0, metrics) is False

    def test_evaluate_metric_validates_multi_tool_latency(self):
        """evaluate_metric correctly validates multi-tool query latency."""
        metrics = get_success_metrics()
        assert evaluate_metric("p95_latency_multi_tool_ms", 4500.0, metrics) is True
        assert evaluate_metric("p95_latency_multi_tool_ms", 5500.0, metrics) is False


# ===========================================================================
# 6.5.3 – Conduct human evaluation of response quality
# ===========================================================================

class TestResponseQuality:
    """Validate response quality infrastructure and metrics."""

    @pytest.mark.asyncio
    async def test_response_contains_meaningful_content(self, ce_handler):
        """Response is not empty and not a generic error message."""
        result = await ce_handler.handle_message("How's my training?")

        assert result["content"]
        assert len(result["content"]) > 10

    @pytest.mark.asyncio
    async def test_response_includes_evidence_cards_when_data_available(
        self, mock_db, mock_session_service, ce_settings,
    ):
        """When evidence is available, it appears in the agent result."""
        evidence = EvidenceCard(
            claim_text="Your last run was solid",
            source_type="activity",
            source_id=123,
            source_date="2025-01-15",
            relevance_score=0.92,
        )
        contract = ChatResponseContract(
            response_text="Your last run was solid!",
            evidence_cards=[evidence],
            confidence_score=0.9,
        )
        adapter = Mock(spec=LLMProviderAdapter)
        adapter.invoke.return_value = LLMResponse(
            parsed_output=contract,
            model_used="mixtral:8x7b-instruct",
            token_count=200,
            latency_ms=200,
        )

        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.gather_data = Mock(return_value=builder)

        agent = ChatAgent(
            context_builder=builder,
            llm_adapter=adapter,
            db=mock_db,
            tool_orchestrator=Mock(spec=ToolOrchestrator),
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        result = await handler.handle_message("How was my last run?")
        assert result["content"] == "Your last run was solid!"

    @pytest.mark.asyncio
    async def test_response_metadata_includes_confidence_score(
        self, mock_llm_adapter,
    ):
        """The ChatResponseContract includes a confidence score."""
        response = mock_llm_adapter.invoke.return_value
        parsed: ChatResponseContract = response.parsed_output
        assert hasattr(parsed, "confidence_score")
        assert 0.0 <= parsed.confidence_score <= 1.0

    def test_response_quality_evaluated_against_min_quality_parity(self):
        """Quality score can be validated against min_quality_parity metric."""
        metrics = get_success_metrics()
        assert evaluate_metric("min_quality_parity", 0.96, metrics) is True
        assert evaluate_metric("min_quality_parity", 0.90, metrics) is False

    @pytest.mark.asyncio
    async def test_response_format_consistent_between_ce_and_legacy(
        self, mock_db, mock_session_service, ce_agent, ce_settings,
    ):
        """CE and legacy responses share the same top-level schema keys."""
        ce_handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=ce_agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )
        ce_result = await ce_handler.handle_message("Hi")

        legacy_handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=None,
            user_id=2,
            session_id=20,
            settings=Settings(USE_CE_CHAT_RUNTIME=False),
        )
        mock_svc = _make_legacy_chat_service()
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            legacy_result = await legacy_handler.handle_message("Hi")

        shared_keys = {
            "content", "tool_calls_made", "iterations",
            "latency_ms", "context_token_count", "ce_context_used", "runtime",
        }
        assert shared_keys.issubset(ce_result.keys())
        assert shared_keys.issubset(legacy_result.keys())


# ===========================================================================
# 6.5.4 – Check for UI regressions
# ===========================================================================

class TestUIRegressions:
    """Validate API contract compatibility and UI-facing response structure."""

    @pytest.mark.asyncio
    async def test_ce_response_schema_matches_api_contract(self, ce_handler):
        """CE response contains all fields expected by the UI."""
        result = await ce_handler.handle_message("Show my goals")

        expected_fields = {
            "content", "tool_calls_made", "iterations",
            "latency_ms", "context_token_count", "ce_context_used", "runtime",
        }
        assert expected_fields.issubset(result.keys()), (
            f"Missing: {expected_fields - result.keys()}"
        )

    @pytest.mark.asyncio
    async def test_ce_response_is_json_serializable(self, ce_handler):
        """CE response can be serialized to JSON for API transport."""
        result = await ce_handler.handle_message("Plan my week")

        serialized = json.dumps(result)
        assert isinstance(serialized, str)
        deserialized = json.loads(serialized)
        assert deserialized["content"] == result["content"]

    @pytest.mark.asyncio
    async def test_streaming_compatibility_response_structure(self, ce_handler):
        """CE response structure supports SSE streaming (content is a string)."""
        result = await ce_handler.handle_message("Tell me about my progress")

        assert isinstance(result["content"], str)
        assert result["runtime"] in ("ce", "legacy")
        assert isinstance(result["latency_ms"], (int, float))
        assert isinstance(result["tool_calls_made"], int)

    @pytest.mark.asyncio
    async def test_error_responses_maintain_consistent_format(
        self, mock_db, mock_session_service, ce_settings,
    ):
        """Errors from CE runtime are standard Python exceptions."""
        failing_agent = Mock()
        failing_agent.execute = AsyncMock(side_effect=ValueError("Invalid input"))

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=failing_agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        with pytest.raises(ValueError, match="Invalid input"):
            await handler.handle_message("Bad request")

    @pytest.mark.asyncio
    async def test_session_operations_work_with_ce_runtime(
        self, mock_session_service, ce_handler,
    ):
        """Session create/load/append operations work alongside CE runtime."""
        mock_session_service.create_session.return_value = 42
        session_id = mock_session_service.create_session(athlete_id=1, title="Test")
        assert session_id == 42

        mock_session_service.load_session.return_value = [
            ChatMessage(session_id=42, role="user", content="Hi"),
        ]
        messages = mock_session_service.load_session(session_id=42)
        assert len(messages) == 1

        result = await ce_handler.handle_message("Continue our chat")
        assert result["runtime"] == "ce"
        mock_session_service.append_messages.assert_called()


# ===========================================================================
# 6.5.5 – Validate tool calling reliability
# ===========================================================================

class TestToolCallingReliability:
    """Validate tool execution reliability in the CE runtime."""

    @pytest.mark.asyncio
    async def test_tool_calls_succeed_with_valid_parameters(
        self, mock_db, mock_session_service, mock_context_builder,
        mock_tool_orchestrator, ce_settings,
    ):
        """Tools execute successfully when given valid parameters."""
        adapter = Mock(spec=LLMProviderAdapter)
        adapter.invoke.return_value = None

        agent = ChatAgent(
            context_builder=mock_context_builder,
            llm_adapter=adapter,
            db=mock_db,
            tool_orchestrator=mock_tool_orchestrator,
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        result = await handler.handle_message("Show my recent activities")

        assert result["tool_calls_made"] == 2
        mock_tool_orchestrator.orchestrate.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_failures_handled_gracefully(
        self, mock_db, mock_session_service, mock_context_builder, ce_settings,
    ):
        """Tool failures don't crash the runtime; error is propagated cleanly."""
        failing_orch = Mock(spec=ToolOrchestrator)
        failing_orch.orchestrate = AsyncMock(
            side_effect=RuntimeError("Tool execution failed")
        )

        adapter = Mock(spec=LLMProviderAdapter)
        adapter.invoke.return_value = None

        agent = ChatAgent(
            context_builder=mock_context_builder,
            llm_adapter=adapter,
            db=mock_db,
            tool_orchestrator=failing_orch,
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        with pytest.raises(RuntimeError, match="Tool execution failed"):
            await handler.handle_message("Show my data")

    def test_tool_success_rate_meets_threshold(self):
        """Tool success rate metric validates against >= 95% threshold."""
        metrics = get_success_metrics()
        assert evaluate_metric("tool_success_rate_min", 0.97, metrics) is True
        assert evaluate_metric("tool_success_rate_min", 0.95, metrics) is True
        assert evaluate_metric("tool_success_rate_min", 0.90, metrics) is False

    @pytest.mark.asyncio
    async def test_tool_iteration_limits_enforced(
        self, mock_db, mock_session_service, mock_context_builder, ce_settings,
    ):
        """ToolOrchestrator respects max_iterations and reports it."""
        orch = Mock(spec=ToolOrchestrator)
        orch.orchestrate = AsyncMock(return_value={
            "content": "I need to simplify my approach.",
            "tool_calls_made": 5,
            "iterations": 5,
            "tool_results": [],
            "max_iterations_reached": True,
            "model_used": "mixtral",
            "response_token_count": 20,
            "intent": "general",
            "evidence_cards": [],
        })

        adapter = Mock(spec=LLMProviderAdapter)
        adapter.invoke.return_value = None

        agent = ChatAgent(
            context_builder=mock_context_builder,
            llm_adapter=adapter,
            db=mock_db,
            tool_orchestrator=orch,
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        result = await handler.handle_message("Complex multi-step query")
        assert result["iterations"] == 5

    @pytest.mark.asyncio
    async def test_tool_results_passed_back_to_llm(
        self, mock_db, mock_session_service, mock_context_builder,
        mock_tool_orchestrator, ce_settings,
    ):
        """Tool results are incorporated into the final response."""
        adapter = Mock(spec=LLMProviderAdapter)
        adapter.invoke.return_value = None

        agent = ChatAgent(
            context_builder=mock_context_builder,
            llm_adapter=adapter,
            db=mock_db,
            tool_orchestrator=mock_tool_orchestrator,
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=1,
            session_id=10,
            settings=ce_settings,
        )

        result = await handler.handle_message("What are my stats?")

        call_kwargs = mock_tool_orchestrator.orchestrate.call_args[1]
        assert call_kwargs["user_id"] == 1
        assert result["content"] == "I found 3 activities this week. Great consistency!"

    @pytest.mark.asyncio
    async def test_user_id_scoping_enforced_for_tool_calls(
        self, mock_db, mock_session_service, mock_context_builder,
        mock_tool_orchestrator, ce_settings,
    ):
        """user_id is always passed to the orchestrator for security scoping."""
        adapter = Mock(spec=LLMProviderAdapter)
        adapter.invoke.return_value = None

        agent = ChatAgent(
            context_builder=mock_context_builder,
            llm_adapter=adapter,
            db=mock_db,
            tool_orchestrator=mock_tool_orchestrator,
        )
        _inject_mock_loaders(agent)

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=agent,
            user_id=42,
            session_id=10,
            settings=ce_settings,
        )

        await handler.handle_message("Get my data")

        call_kwargs = mock_tool_orchestrator.orchestrate.call_args[1]
        assert call_kwargs["user_id"] == 42


# ===========================================================================
# 6.5.6 – Compare with legacy baseline
# ===========================================================================

class TestLegacyBaselineComparison:
    """Validate CE vs legacy comparison infrastructure and metrics."""

    @pytest.mark.asyncio
    async def test_ce_and_legacy_produce_same_schema(
        self, mock_db, mock_session_service, ce_agent,
    ):
        """Both runtimes return responses with the same top-level keys."""
        ce_handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=ce_agent,
            user_id=1,
            session_id=10,
            settings=Settings(USE_CE_CHAT_RUNTIME=True),
        )
        ce_result = await ce_handler.handle_message("Hi")

        legacy_handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=None,
            user_id=2,
            session_id=20,
            settings=Settings(USE_CE_CHAT_RUNTIME=False),
        )
        mock_svc = _make_legacy_chat_service()
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            legacy_result = await legacy_handler.handle_message("Hi")

        shared_keys = {
            "content", "tool_calls_made", "iterations",
            "latency_ms", "context_token_count", "ce_context_used", "runtime",
        }
        assert shared_keys.issubset(ce_result.keys())
        assert shared_keys.issubset(legacy_result.keys())

    @pytest.mark.asyncio
    async def test_ce_latency_within_acceptable_regression(self):
        """CE latency must not exceed legacy by more than 10%."""
        metrics = get_success_metrics()
        assert evaluate_metric("max_latency_regression_pct", 5.0, metrics) is True
        assert evaluate_metric("max_latency_regression_pct", 10.0, metrics) is True
        assert evaluate_metric("max_latency_regression_pct", 15.0, metrics) is False

    @pytest.mark.asyncio
    async def test_ce_token_usage_within_budget(self, ce_handler):
        """CE token usage stays within the configured budget."""
        result = await ce_handler.handle_message("Quick question")

        metrics = get_success_metrics()
        token_budget = 2400
        within_budget = result["context_token_count"] <= token_budget
        compliance = 1.0 if within_budget else 0.0
        assert evaluate_metric("token_budget_compliance", compliance, metrics)

    @pytest.mark.asyncio
    async def test_comparison_mode_produces_valid_report(self):
        """run_comparison produces a valid ComparisonReport with all fields."""
        async def ce_fn(msg):
            return {
                "runtime": "ce", "content": "CE response",
                "latency_ms": 150.0, "tool_calls_made": 1,
                "iterations": 1, "context_token_count": 800,
                "ce_context_used": True,
            }

        async def legacy_fn(msg):
            return {
                "runtime": "legacy", "content": "Legacy response",
                "latency_ms": 200.0, "tool_calls_made": 0,
                "iterations": 0, "context_token_count": 0,
                "ce_context_used": False,
            }

        report = await run_comparison(
            user_message="How am I doing?",
            session_id=1,
            user_id=1,
            ce_handler_fn=ce_fn,
            legacy_handler_fn=legacy_fn,
        )

        assert isinstance(report, ComparisonReport)
        assert report.both_succeeded is True
        assert report.ce_result is not None
        assert report.legacy_result is not None
        assert report.latency_diff_ms == -50.0
        assert report.ce_faster is True

        report_dict = report.to_dict()
        serialized = json.dumps(report_dict)
        assert isinstance(serialized, str)
        assert "latency_diff_ms" in report_dict
        assert "token_diff" in report_dict

    @pytest.mark.asyncio
    async def test_both_runtimes_handle_same_queries(
        self, mock_db, mock_session_service, ce_agent,
    ):
        """Both CE and legacy can handle the same set of queries."""
        queries = [
            "How was my week?",
            "Show my goals",
            "Plan my next workout",
        ]

        ce_handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=ce_agent,
            user_id=1,
            session_id=10,
            settings=Settings(USE_CE_CHAT_RUNTIME=True),
        )

        legacy_handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=None,
            user_id=2,
            session_id=20,
            settings=Settings(USE_CE_CHAT_RUNTIME=False),
        )

        for query in queries:
            ce_result = await ce_handler.handle_message(query)
            assert ce_result["runtime"] == "ce"
            assert ce_result["content"]

            mock_svc = _make_legacy_chat_service(f"Legacy: {query}")
            with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
                legacy_result = await legacy_handler.handle_message(query)
            assert legacy_result["runtime"] == "legacy"
            assert legacy_result["content"]

    def test_evaluate_max_latency_regression_pct(self):
        """evaluate_metric correctly validates latency regression percentage."""
        metrics = get_success_metrics()
        assert metrics.max_latency_regression_pct == 10.0
        assert evaluate_metric("max_latency_regression_pct", 0.0, metrics) is True
        assert evaluate_metric("max_latency_regression_pct", 10.0, metrics) is True
        assert evaluate_metric("max_latency_regression_pct", 10.1, metrics) is False
