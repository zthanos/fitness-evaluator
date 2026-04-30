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
import json
import time
import uuid
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
        self.llm_client = llm_client  # primary reasoning model for synthesis

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
            context = await self._build_context(
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
            # Skip the structured-output path when the intent has a tool hint —
            # those queries need the ReAct loop to call actual tools.
            from app.ai.retrieval.intent_router import INTENT_TOOL_HINT
            intent_needs_tools = bool(
                INTENT_TOOL_HINT.get(getattr(self.context_builder, "last_intent", None))
            )
            llm_response = None if intent_needs_tools else self._invoke_llm(
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
                self._record_trace(
                    response=response,
                    user_message=user_message,
                    session_id=session_id,
                    user_id=user_id,
                    intent=getattr(self.context_builder, "last_intent", "unknown"),
                    intent_used_tools=False,
                )
                return response

            # --- Step 3: Fallback to ToolOrchestrator path ---
            # Save the full CE system prompt for the primary-model synthesis step.
            # The tool-calling subagent gets a lean prompt only — it has a small
            # context window (e.g. Llama 3.1 8B @ 8 K tokens) and only needs to
            # know which tool to call, not the entire coaching context.
            full_context_messages = context.to_messages()
            _context_system = (
                full_context_messages[0]["content"]
                if full_context_messages and full_context_messages[0].get("role") == "system"
                else ""
            )

            tool_hint = INTENT_TOOL_HINT.get(
                getattr(self.context_builder, "last_intent", None)
            )
            user_content = (
                f"[Suggested tool: {tool_hint}]\n{user_message}"
                if tool_hint and intent_needs_tools
                else user_message
            )

            # Lean conversation for the tool-calling subagent.
            # Keep this short — the model has a small context window.
            conversation = [
                {
                    "role": "system",
                    "content": (
                        "You are a fitness data retrieval assistant. "
                        "Call the correct tool to answer the user's question. "
                        "Rules you MUST follow:\n"
                        "- NEVER ask for clarification. Make a reasonable assumption and call the tool immediately.\n"
                        "- ALL distance values are in METERS (e.g. 55 km = 55000, 10 km = 10000).\n"
                        "- ALL duration values are in SECONDS (e.g. 1 hour = 3600).\n"
                        "- For 'longest/biggest/most distance' questions: sort by distance_m desc.\n"
                        "- For ride questions: filter sport_type eq Ride.\n"
                        "- For run questions: filter sport_type eq Run.\n"
                        "- Default limit: 10 results unless the user specifies otherwise.\n"
                        "- Call the tool now. Do not respond with text first."
                    ),
                },
                {"role": "user", "content": user_content},
            ]

            result = await self._orchestrate(
                conversation=conversation,
                user_id=user_id,
            )

            # ── Primary-model synthesis ──────────────────────────────────────
            # The tool-calling subagent (e.g. Llama 3.1 8B) is optimised for
            # emitting tool_calls JSON, not for rich coaching prose.  After it
            # has collected the data, hand the tool results to the primary
            # reasoning model so it can synthesise a proper coaching response.
            if result.get("tool_calls_made", 0) > 0:
                synth = await self._synthesize_with_primary(
                    system_message=_context_system,
                    user_message=user_message,
                    tool_results=self.tool_orchestrator.invocation_log,
                )
                if synth:
                    result["content"] = synth

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
            self._record_trace(
                response=response,
                user_message=user_message,
                session_id=session_id,
                user_id=user_id,
                intent=getattr(self.context_builder, "last_intent", "unknown"),
                intent_used_tools=intent_needs_tools,
            )
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

    async def _build_context(
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
        from app.ai.retrieval.llm_intent_classifier import classify_intent

        history_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in conversation_history[-10:]
        ]

        # Classify intent with the LLM; keyword matching is the fallback inside classify_intent
        intent = await classify_intent(user_message)

        # Populate context layers
        if system_instructions:
            enhanced_system = system_instructions
            if athlete_summary:
                enhanced_system = (
                    f"{system_instructions}\n\n## Athlete Profile\n{athlete_summary}"
                )
            fitness_snapshot = self._fitness_state_snapshot(user_id)
            if fitness_snapshot:
                enhanced_system = f"{enhanced_system}\n\n## Current Fitness State\n{fitness_snapshot}"
            self.context_builder.add_system_instructions(enhanced_system)

        if task_instructions:
            self.context_builder.add_task_instructions(task_instructions)

        if domain_knowledge:
            self.context_builder.add_domain_knowledge(domain_knowledge)

        # Intent-aware retrieval + dynamic history selection (intent pre-classified above)
        self.context_builder.gather_data(
            query=user_message,
            athlete_id=user_id,
            conversation_history=history_dicts,
            intent=intent,
        )

        return self.context_builder.build()

    def _fitness_state_snapshot(self, user_id: int) -> str:
        """Return a one-line fitness state summary from the persisted AthleteFitnessState, or ''."""
        try:
            from app.models.athlete_fitness_state import AthleteFitnessState
            row = (
                self.db.query(AthleteFitnessState)
                .filter(AthleteFitnessState.athlete_id == user_id)
                .first()
            )
            if not row:
                return ""
            parts = []
            if row.athlete_classification:
                parts.append(f"Type: {row.athlete_classification}")
            if row.fitness_score is not None:
                parts.append(f"Fitness score: {row.fitness_score:.0f}/100")
            if row.fatigue_level:
                parts.append(f"Fatigue: {row.fatigue_level}")
            if row.current_limiter:
                parts.append(f"Limiter: {row.current_limiter.replace('_', ' ')}")
            if row.acwr_ratio is not None:
                parts.append(f"ACWR: {row.acwr_ratio:.2f}")
            return " | ".join(parts) if parts else ""
        except Exception:
            return ""

    async def _synthesize_with_primary(
        self,
        system_message: str,
        user_message: str,
        tool_results: list,
    ) -> str:
        """Re-synthesize the final coaching response using the primary reasoning model.

        The tool-calling subagent collected the data; this method takes those
        results and asks the reasoning model to turn them into a proper coaching
        answer, following the full system prompt.
        """
        # Build a readable tool-results block to inject into context
        result_parts = []
        for r in tool_results:
            if r.success and r.result is not None:
                try:
                    result_json = json.dumps(r.result, default=str, indent=2)
                except Exception:
                    result_json = str(r.result)
                result_parts.append(
                    f"### {r.tool_name} (retrieved data)\n```json\n{result_json}\n```"
                )

        if not result_parts:
            return ""

        tool_block = (
            "## Data Retrieved for This Request\n\n"
            + "\n\n".join(result_parts)
            + "\n\nUse the above data to answer the athlete's question directly and specifically."
        )

        messages = [
            {
                "role": "system",
                "content": (
                    f"{system_message}\n\n"
                    f"{tool_block}\n\n"
                    "IMPORTANT: Respond in clear, conversational natural language. "
                    "Do NOT output JSON, code blocks, or structured data formats. "
                    "Speak directly to the athlete as a coach would."
                ),
            },
            {"role": "user", "content": user_message},
        ]

        try:
            resp = await self.llm_client.chat_completion(
                messages=messages,
                tools=None,
                max_tokens=1024,
                temperature=0.7,
            )
            content = resp.get("content") or ""
            # Strip <think>...</think> blocks emitted by reasoning models
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if content:
                logger.debug("Primary synthesis produced %d chars", len(content))
            return content
        except Exception as exc:
            logger.warning(
                "Primary synthesis failed (%s) — keeping subagent answer", exc
            )
            return ""

    def _record_trace(
        self,
        response: Dict[str, Any],
        user_message: str,
        session_id: int,
        user_id: int,
        intent: Any,
        intent_used_tools: bool,
    ) -> None:
        """Serialize execution metadata into a trace dict and hand it to TraceCollector."""
        try:
            from app.services.trace_collector import traces

            def _step_dict(s) -> dict:
                return {
                    "step":       s.step.value,
                    "iteration":  s.iteration,
                    "detail":     s.detail,
                    "timestamp":  s.timestamp,
                    "latency_ms": round(s.latency_ms, 1),
                    "metadata":   s.metadata,
                }

            def _tool_dict(r) -> dict:
                preview = ""
                if r.result is not None:
                    try:
                        raw = json.dumps(r.result, default=str)
                        preview = raw[:500] + ("…" if len(raw) > 500 else "")
                    except Exception:
                        preview = str(r.result)[:500]
                return {
                    "tool_name":   r.tool_name,
                    "parameters":  r.parameters,
                    "result_preview": preview,
                    "error":       r.error,
                    "error_type":  r.error_type.value if r.error_type else None,
                    "latency_ms":  round(r.latency_ms, 1),
                    "success":     r.success,
                    "iteration":   r.iteration,
                }

            react_steps = []
            tool_calls = []
            if intent_used_tools:
                react_steps = [_step_dict(s) for s in self.tool_orchestrator.react_log]
                tool_calls  = [_tool_dict(r) for r in self.tool_orchestrator.invocation_log]

            layer_tokens: Dict[str, int] = {}
            try:
                if hasattr(self.context_builder, "get_layer_tokens"):
                    layer_tokens = self.context_builder.get_layer_tokens()
            except Exception:
                pass

            intent_str = intent.value if hasattr(intent, "value") else str(intent)

            traces.record({
                "trace_id":           str(uuid.uuid4()),
                "session_id":         session_id,
                "user_id":            user_id,
                "timestamp":          time.time(),
                "user_message":       user_message[:200],
                "intent":             intent_str,
                "intent_used_tools":  intent_used_tools,
                "context_tokens":     layer_tokens,
                "total_context_tokens": sum(layer_tokens.values()),
                "react_steps":        react_steps,
                "tool_calls":         tool_calls,
                "total_latency_ms":   round(response.get("total_latency_ms") or response.get("latency_ms", 0), 1),
                "retrieval_latency_ms": round(response.get("retrieval_latency_ms") or 0, 1),
                "model_latency_ms":   round(response.get("model_latency_ms") or 0, 1),
                "model_used":         response.get("model_used", "unknown"),
                "final_content":      response.get("content", "")[:300],
                "tool_calls_made":    response.get("tool_calls_made", 0),
                "iterations":         response.get("iterations", 0),
            })
        except Exception as exc:
            logger.debug("Trace recording failed (non-fatal): %s", exc)

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
