"""ChatAgent - Runtime execution owner for chat flow.

Centralizes chat execution by coordinating context building, LLM invocation
via LLMAdapter, and tool orchestration via ToolOrchestrator.

Flow:
1. Build context via ChatContextBuilder
2. Invoke LLMAdapter.invoke() with ChatResponseContract for structured output
3. If tool orchestration is needed, delegate to ToolOrchestrator
4. Return final response with metadata from LLMResponse

Requirements: 3.1, 3.2 (Phase 3), 4.5 (Phase 4), 5.1 (Phase 5)
"""
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.ai.context.chat_context import ChatContextBuilder
from app.ai.context.builder import Context
from app.ai.adapter.llm_adapter import LLMProviderAdapter, LLMResponse
from app.ai.contracts.chat_contract import ChatResponseContract
from app.models.chat_message import ChatMessage
from app.services.chat_tools import get_tool_definitions
from app.services.tool_orchestrator import ToolOrchestrator

logger = logging.getLogger(__name__)


class ChatAgent:
    """Runtime execution owner for chat flow.

    Owns:
        - Requesting context from ``ChatContextBuilder``
        - Invoking LLM through ``LLMAdapter.invoke()`` with ``ChatResponseContract``
        - Checking for and delegating tool calls to ``ToolOrchestrator``
        - Collecting metadata (latency, tokens, model, iterations) from ``LLMResponse``

    Does NOT own:
        - Session persistence → ``ChatSessionService``
        - Context layer assembly internals → ``ChatContextBuilder``
        - Individual tool implementation → ``chat_tools``
        - Direct model invocation details → ``LLMAdapter``

    Contract (see ``app.services.contracts``):
        Input:  ``AgentInput`` (or the equivalent positional args)
            - ``conversation_history`` is ``List[ChatMessage]`` from
              ``ChatSessionService.get_active_buffer()``.
        Output: ``AgentResult`` dict (matches ``AgentResult.to_dict()``).
        Errors: Wrapped in ``AgentError`` categories; the handler inspects
            ``AgentError.kind`` to decide retry / user-message / escalation.
    """

    def __init__(
        self,
        context_builder: ChatContextBuilder,
        llm_adapter: LLMProviderAdapter,
        db: Any,
        tool_orchestrator: Optional[ToolOrchestrator] = None,
        llm_client: Any = None,
    ):
        """
        Initialize ChatAgent.

        Args:
            context_builder: CE context builder for structured context assembly.
            llm_adapter: LLM adapter with fallback for structured output calls.
                Used for initial response generation via ``invoke()``.
            db: SQLAlchemy database session (needed for tool execution).
            tool_orchestrator: ToolOrchestrator for multi-step tool execution.
                When ``None`` a default instance is created from ``llm_client``
                and ``db``.
            llm_client: Legacy LLM client for tool-calling chat completions
                (used by ToolOrchestrator). Required when ``tool_orchestrator``
                is ``None``.
        """
        self.context_builder = context_builder
        self.llm_adapter = llm_adapter
        self.db = db

        # Build a default ToolOrchestrator when none is injected
        if tool_orchestrator is None:
            if llm_client is None:
                raise ValueError(
                    "Either tool_orchestrator or llm_client must be provided"
                )
            tool_orchestrator = ToolOrchestrator(
                llm_client=llm_client,
                db=db,
            )
        self.tool_orchestrator = tool_orchestrator

        # Lazy-loaded CE loaders (initialised on first use)
        self._system_loader = None
        self._task_loader = None
        self._domain_loader = None
        self._behavior_summary = None

    async def execute(
        self,
        user_message: str,
        session_id: int,
        user_id: int,
        conversation_history: List[ChatMessage],
        system_instructions: str = "",
        task_instructions: str = "",
        domain_knowledge: Optional[Dict[str, Any]] = None,
        athlete_summary: str = "",
    ) -> Dict[str, Any]:
        """Execute a chat request through the full CE pipeline.

        This is the primary entry point called by ``ChatMessageHandler``.
        The handler supplies ``conversation_history`` obtained from
        ``ChatSessionService.get_active_buffer()`` and consumes the
        returned dict (whose shape matches ``AgentResult.to_dict()``).

        The method first attempts a structured response via
        ``LLMAdapter.invoke()`` with ``ChatResponseContract``. If the
        response indicates tool usage is needed (via the ToolOrchestrator
        path), it delegates accordingly.

        Args:
            user_message: Current user query text.
            session_id: Numeric chat-session identifier.
            user_id: Numeric athlete / user identifier.
            conversation_history: Ordered ``ChatMessage`` objects from the
                session buffer (oldest first).
            system_instructions: Pre-loaded system prompt text.
            task_instructions: Pre-loaded task prompt text.
            domain_knowledge: Pre-loaded domain knowledge dict.
            athlete_summary: Pre-generated athlete behaviour summary.

        Returns:
            Dict matching the ``AgentResult`` schema::

                {
                    "content": str,
                    "tool_calls_made": int,
                    "iterations": int,
                    "latency_ms": float,
                    "model_used": str,
                    "context_token_count": int,
                    "response_token_count": int,
                    "intent": str,
                    "evidence_cards": List[Dict],
                }
        """
        start_time = time.time()

        try:
            # --- Step 0: Load CE defaults for any missing layers ---
            (
                system_instructions,
                task_instructions,
                domain_knowledge,
                athlete_summary,
            ) = self._load_defaults(
                user_id=user_id,
                session_id=session_id,
                system_instructions=system_instructions,
                task_instructions=task_instructions,
                domain_knowledge=domain_knowledge,
                athlete_summary=athlete_summary,
            )

            # --- Step 1: Build context via ChatContextBuilder ---
            retrieval_start = time.time()
            context = self._build_context(
                user_message=user_message,
                user_id=user_id,
                conversation_history=conversation_history,
                system_instructions=system_instructions,
                task_instructions=task_instructions,
                domain_knowledge=domain_knowledge,
                athlete_summary=athlete_summary,
            )
            retrieval_latency_ms = (time.time() - retrieval_start) * 1000

            # --- Step 2: Try structured response via LLMAdapter ---
            llm_response = self._invoke_llm(
                context=context,
                user_id=user_id,
            )

            if llm_response is not None:
                # Structured response succeeded — extract metadata
                parsed: ChatResponseContract = llm_response.parsed_output
                latency_ms = (time.time() - start_time) * 1000

                evidence_dicts = [
                    ec.model_dump() for ec in (parsed.evidence_cards or [])
                ]

                response = {
                    "content": parsed.response_text,
                    "tool_calls_made": 0,
                    "iterations": 0,
                    "latency_ms": latency_ms,
                    "model_used": llm_response.model_used,
                    "context_token_count": context.token_count,
                    "response_token_count": llm_response.token_count - context.token_count,
                    "intent": "general",
                    "evidence_cards": evidence_dicts,
                    "retrieval_latency_ms": retrieval_latency_ms,
                    "model_latency_ms": llm_response.latency_ms,
                    "total_latency_ms": latency_ms,
                }

                self._log_completion(response, user_id, session_id, latency_ms)
                return response

            # --- Step 3: Fallback to ToolOrchestrator path ---
            conversation = context.to_messages()
            conversation.append({"role": "user", "content": user_message})

            result = await self._orchestrate(
                conversation=conversation,
                user_id=user_id,
            )

            latency_ms = (time.time() - start_time) * 1000

            if latency_ms > 3000:
                logger.warning(
                    "ChatAgent latency exceeded 3 s target: %.0f ms",
                    latency_ms,
                    extra={"user_id": user_id, "session_id": session_id},
                )

            response = {
                "content": result["content"],
                "tool_calls_made": result.get("tool_calls_made", 0),
                "iterations": result.get("iterations", 0),
                "latency_ms": latency_ms,
                "model_used": result.get("model_used", "unknown"),
                "context_token_count": context.token_count,
                "response_token_count": result.get("response_token_count", 0),
                "intent": result.get("intent", "general"),
                "evidence_cards": result.get("evidence_cards", []),
                "retrieval_latency_ms": retrieval_latency_ms,
                "model_latency_ms": result.get("model_latency_ms"),
                "total_latency_ms": latency_ms,
            }

            self._log_completion(response, user_id, session_id, latency_ms)
            return response

        except Exception:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "ChatAgent execution failed after %.0f ms",
                latency_ms,
                extra={"user_id": user_id, "session_id": session_id},
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _invoke_llm(
        self,
        context: Any,
        user_id: int,
    ) -> Optional[LLMResponse]:
        """Invoke LLMAdapter with ChatResponseContract.

        Returns ``None`` when the adapter is not available (graceful
        fallback to ToolOrchestrator path).
        """
        if self.llm_adapter is None:
            return None

        try:
            return self.llm_adapter.invoke(
                context=context,
                contract=ChatResponseContract,
                operation_type="chat_response",
                athlete_id=user_id,
            )
        except Exception as exc:
            logger.warning(
                "LLMAdapter.invoke() failed, falling back to orchestrator: %s",
                exc,
                extra={"user_id": user_id},
            )
            return None

    def _log_completion(
        self,
        response: Dict[str, Any],
        user_id: int,
        session_id: int,
        latency_ms: float,
    ) -> None:
        """Log a successful execution summary."""
        logger.info(
            "ChatAgent executed in %.0f ms (tools=%d, iters=%d, model=%s)",
            latency_ms,
            response["tool_calls_made"],
            response["iterations"],
            response["model_used"],
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "latency_ms": latency_ms,
                "model_used": response["model_used"],
            },
        )

    def _ensure_loaders(self) -> None:
        """Lazily initialise CE loaders on first use."""
        if self._system_loader is None:
            from app.ai.prompts.system_loader import SystemInstructionsLoader
            from app.ai.prompts.task_loader import TaskInstructionsLoader
            from app.ai.config.domain_loader import DomainKnowledgeLoader
            from app.ai.context.athlete_behavior_summary import AthleteBehaviorSummary

            self._system_loader = SystemInstructionsLoader()
            self._task_loader = TaskInstructionsLoader()
            self._domain_loader = DomainKnowledgeLoader()
            self._behavior_summary = AthleteBehaviorSummary(self.db)

    def _load_defaults(
        self,
        user_id: int,
        session_id: int,
        system_instructions: str,
        task_instructions: str,
        domain_knowledge: Optional[Dict[str, Any]],
        athlete_summary: str,
    ) -> tuple:
        """Return CE defaults for any values not explicitly provided."""
        self._ensure_loaders()

        if not system_instructions:
            system_instructions = self._system_loader.load(version="1.0.0")
        if not task_instructions:
            task_instructions = self._task_loader.load(
                operation="chat_response",
                version="1.0.0",
                params={
                    "athlete_id": user_id,
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )
        if domain_knowledge is None:
            dk = self._domain_loader.load()
            domain_knowledge = dk.to_dict() if hasattr(dk, "to_dict") else dk
        if not athlete_summary:
            athlete_summary = self._behavior_summary.generate_summary(user_id)

        return system_instructions, task_instructions, domain_knowledge, athlete_summary

    def _build_context(
        self,
        user_message: str,
        user_id: int,
        conversation_history: List[ChatMessage],
        system_instructions: str,
        task_instructions: str,
        domain_knowledge: Optional[Dict[str, Any]],
        athlete_summary: str,
    ) -> 'Context':
        """Build a validated, token-budgeted Context via ChatContextBuilder."""
        history_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in conversation_history[-10:]
        ]

        # Populate context layers
        if system_instructions:
            enhanced_system = system_instructions
            if athlete_summary:
                enhanced_system = (
                    f"{system_instructions}\n\n## Athlete Profile\n{athlete_summary}"
                )
            self.context_builder.add_system_instructions(enhanced_system)

        if task_instructions:
            self.context_builder.add_task_instructions(task_instructions)

        if domain_knowledge:
            self.context_builder.add_domain_knowledge(domain_knowledge)

        # Intent-aware retrieval + dynamic history selection
        self.context_builder.gather_data(
            query=user_message,
            athlete_id=user_id,
            conversation_history=history_dicts,
        )

        return self.context_builder.build()

    async def _orchestrate(
        self,
        conversation: List[Dict[str, str]],
        user_id: int,
    ) -> Dict[str, Any]:
        """Delegate tool orchestration to ToolOrchestrator.

        Passes the conversation, tool definitions, and user_id to the
        orchestrator which implements the full ReAct loop with failure
        policies, parameter validation, and iteration limits.
        """
        return await self.tool_orchestrator.orchestrate(
            conversation=conversation,
            tool_definitions=get_tool_definitions(),
            user_id=user_id,
        )
