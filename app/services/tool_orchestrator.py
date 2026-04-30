"""ToolOrchestrator - Multi-step tool execution with ReAct pattern.

Owns the iterative tool-calling loop: send conversation to LLM, check for
tool_calls, execute them sequentially, append results, and repeat until the
LLM produces a final text answer or the iteration cap is reached.

Flow (ReAct):
    Think  → LLM decides which tool(s) to call (or to answer directly)
    Act    → Execute requested tools sequentially
    Observe→ Append tool results to conversation
    Repeat → Until final answer or max_iterations

Requirements: 4.1, 4.2, 4.3 (Phase 4)
"""

import json
import time
import logging
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.services.chat_tools import execute_tool

logger = logging.getLogger(__name__)

# Max iterations hard ceiling to prevent misconfiguration
_MAX_ITERATIONS_CEILING = 20


# ---------------------------------------------------------------------------
# Configuration & types
# ---------------------------------------------------------------------------


class FailurePolicy(str, Enum):
    """How the orchestrator reacts when a tool call fails.

    Members:
        FAIL_FAST: Abort the entire orchestration immediately.
        RETRY: Re-invoke the LLM with the error so it can try again.
        SKIP: Record the error as a tool result and continue.
    """

    FAIL_FAST = "fail_fast"
    RETRY = "retry"
    SKIP = "skip"


class ReActStep(str, Enum):
    """Phases of the ReAct loop."""

    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"


@dataclass
class ReActStepRecord:
    """Structured log entry for a single ReAct phase."""

    step: ReActStep
    iteration: int
    detail: str
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolInvocationRecord:
    """Structured log entry for a single tool invocation."""

    tool_name: str
    parameters: Dict[str, Any]
    result: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    iteration: int = 0
    success: bool = True
    user_id: Optional[int] = None
    timestamp: float = field(default_factory=time.time)
    error_type: Optional['ToolErrorType'] = None
    is_retryable: bool = False
    failure_detail: Optional['ToolFailureDetail'] = None


class ToolOrchestrationError(Exception):
    """Raised when tool orchestration fails irrecoverably."""
    pass


class ToolParameterValidationError(Exception):
    """Raised when tool parameters fail schema validation."""
    pass


class ToolErrorType(str, Enum):
    """Classification of tool execution errors.

    Used to provide structured error information to the LLM so it can
    decide whether to retry, use a different tool, or give up.
    """

    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    PERMISSION_ERROR = "permission_error"
    NOT_FOUND_ERROR = "not_found_error"
    CONNECTION_ERROR = "connection_error"
    RUNTIME_ERROR = "runtime_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ToolFailureDetail:
    """Structured detail about a tool failure for logging and LLM context."""

    tool_name: str
    error_type: ToolErrorType
    error_message: str
    is_retryable: bool
    iteration: int
    user_id: Optional[int] = None
    parameters: Optional[Dict[str, Any]] = None
    traceback_summary: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# ToolOrchestrator
# ---------------------------------------------------------------------------


class ToolOrchestrator:
    """Multi-step tool execution with ReAct pattern.

    Responsibilities:
        - Execute zero, one, or many tool calls per request
        - Support sequential tool chains (later tools see earlier results)
        - Enforce configurable iteration limits (default 5)
        - Handle tool failures according to ``failure_policy``
        - Log every tool invocation for debugging / telemetry

    Does NOT own:
        - Context building → ``ChatContextBuilder``
        - Session persistence → ``ChatSessionService``
        - Individual tool implementations → ``chat_tools``

    Usage::

        orchestrator = ToolOrchestrator(llm_client, db)
        result = await orchestrator.orchestrate(
            conversation=messages,
            tool_definitions=get_tool_definitions(),
            user_id=7,
        )
    """

    def __init__(
        self,
        llm_client: Any,
        db: Any,
        max_iterations: int = 5,
        failure_policy: FailurePolicy = FailurePolicy.SKIP,
    ):
        """
        Args:
            llm_client: LLM client exposing ``chat_completion(messages, tools)``.
            db: SQLAlchemy database session for tool execution.
            max_iterations: Upper bound on Think→Act→Observe cycles (1–20).
            failure_policy: How to handle individual tool failures.

        Raises:
            ValueError: If max_iterations is outside the allowed range.
        """
        if not isinstance(max_iterations, int) or max_iterations < 1:
            raise ValueError(
                f"max_iterations must be a positive integer, got {max_iterations!r}"
            )
        if max_iterations > _MAX_ITERATIONS_CEILING:
            raise ValueError(
                f"max_iterations cannot exceed {_MAX_ITERATIONS_CEILING}, "
                f"got {max_iterations}"
            )
        if isinstance(failure_policy, str):
            failure_policy = FailurePolicy(failure_policy)

        self.llm_client = llm_client
        self.db = db
        self.max_iterations = max_iterations
        self.failure_policy = failure_policy
        self._invocation_log: List[ToolInvocationRecord] = []
        self._react_log: List[ReActStepRecord] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def orchestrate(
        self,
        conversation: List[Dict[str, str]],
        tool_definitions: List[Dict[str, Any]],
        user_id: int,
    ) -> Dict[str, Any]:
        """Execute multi-step tool orchestration with ReAct pattern.

        The loop follows the ReAct framework:
            Think  → LLM decides which tool(s) to call (or to answer directly)
            Act    → Execute requested tools sequentially
            Observe→ Append tool results to conversation
            Repeat → Until final answer or max_iterations

        Each phase is logged as a :class:`ReActStepRecord` for full
        transparency and debugging.

        Args:
            conversation: Current conversation messages (mutated in-place).
            tool_definitions: Tool schemas for the LLM.
            user_id: Athlete / user ID for tool scoping.

        Returns:
            Dict matching the ``AgentResult`` shape::

                {
                    "content": str,
                    "tool_calls_made": int,
                    "iterations": int,
                    "tool_results": List[Dict],
                    "max_iterations_reached": bool,
                    "model_used": str,
                    "response_token_count": int,
                    "intent": "general",
                    "evidence_cards": [],
                }
        """
        self._invocation_log.clear()
        self._react_log.clear()
        tool_calls_made = 0
        tool_results: List[Dict[str, Any]] = []
        orchestration_start = time.time()

        # ── user_id scoping enforcement (4.3.4) ────────────────────
        if user_id is None:
            raise ToolOrchestrationError(
                "user_id is required for tool orchestration (security scoping)"
            )

        # ── Build tool schema index for parameter validation (4.3.5)
        tool_schemas: Dict[str, Dict[str, Any]] = {}
        for tdef in (tool_definitions or []):
            func = tdef.get("function", {})
            name = func.get("name")
            if name:
                tool_schemas[name] = func.get("parameters", {})

        logger.debug(
            "ReAct orchestration started (max_iterations=%d, failure_policy=%s)",
            self.max_iterations,
            self.failure_policy.value,
            extra={"user_id": user_id},
        )

        for iteration in range(self.max_iterations):
            iter_num = iteration + 1

            # ── THINK: ask the LLM what to do next ──────────────────
            think_start = time.time()
            tool_names_requested: List[str] = []

            logger.debug(
                "[THINK] iteration %d/%d – invoking LLM for reasoning",
                iter_num,
                self.max_iterations,
                extra={"user_id": user_id, "react_step": "think"},
            )

            response = await self.llm_client.chat_completion(
                messages=conversation,
                tools=tool_definitions or None,
            )

            think_latency = (time.time() - think_start) * 1000
            has_tool_calls = bool(response.get("tool_calls"))

            if has_tool_calls:
                tool_names_requested = [
                    tc["function"]["name"]
                    for tc in response["tool_calls"]
                    if "function" in tc
                ]
                think_detail = (
                    f"LLM requested {len(tool_names_requested)} tool(s): "
                    f"{', '.join(tool_names_requested)}"
                )
            else:
                think_detail = "LLM produced final answer (no tool calls)"

            self._log_react_step(
                step=ReActStep.THINK,
                iteration=iter_num,
                detail=think_detail,
                latency_ms=think_latency,
                metadata={
                    "tool_calls_requested": tool_names_requested,
                    "has_content": bool(response.get("content")),
                    "model": response.get("model", "unknown"),
                },
            )

            # Append assistant message to conversation
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.get("content", ""),
            }
            if has_tool_calls:
                assistant_msg["tool_calls"] = response["tool_calls"]
            conversation.append(assistant_msg)

            # ── Termination: no tool calls → final answer ───────────
            if not has_tool_calls:
                self._log_debug_summary(
                    user_id=user_id,
                    iterations=iter_num,
                    tool_calls_made=tool_calls_made,
                    orchestration_start=orchestration_start,
                    max_reached=False,
                )
                return self._build_result(
                    content=response.get("content", ""),
                    tool_calls_made=tool_calls_made,
                    iterations=iter_num,
                    tool_results=tool_results,
                    max_iterations_reached=False,
                    model_used=response.get("model", "unknown"),
                )

            # ── ACT: execute each tool call sequentially ────────────
            for tool_call in response["tool_calls"]:
                act_start = time.time()

                # ── Parameter validation (4.3.5) ────────────────────
                tool_name = tool_call["function"]["name"]
                try:
                    raw_args = json.loads(
                        tool_call["function"].get("arguments", "{}")
                    )
                except (json.JSONDecodeError, KeyError):
                    raw_args = {}

                # Small LLMs often double-encode arrays/objects as JSON strings
                # or emit integers as strings. Coerce before validating so the
                # format mismatch doesn't burn a retry iteration.
                raw_args = self._coerce_tool_params(raw_args, tool_schemas, tool_name)
                tool_call["function"]["arguments"] = json.dumps(raw_args)

                validation_error = self._validate_tool_params(
                    tool_name, raw_args, tool_schemas
                )
                if validation_error:
                    logger.warning(
                        "Parameter validation failed for %s: %s",
                        tool_name,
                        validation_error,
                        extra={"user_id": user_id, "tool_name": tool_name},
                    )
                    record = ToolInvocationRecord(
                        tool_name=tool_name,
                        parameters=raw_args,
                        error=f"Validation error: {validation_error}",
                        latency_ms=0.0,
                        iteration=iter_num,
                        success=False,
                        user_id=user_id,
                        error_type=ToolErrorType.VALIDATION_ERROR,
                        is_retryable=False,
                    )
                else:
                    record = await self._execute_single_tool(
                        tool_call=tool_call,
                        user_id=user_id,
                        iteration=iter_num,
                    )

                self._invocation_log.append(record)
                act_latency = (time.time() - act_start) * 1000

                if record.success:
                    tool_calls_made += 1
                    tool_results.append({
                        "tool_name": record.tool_name,
                        "result": record.result,
                        "latency_ms": record.latency_ms,
                    })
                    act_detail = (
                        f"Executed {record.tool_name} successfully "
                        f"in {record.latency_ms:.0f}ms"
                    )
                else:
                    tool_results.append({
                        "tool_name": record.tool_name,
                        "error": record.error,
                        "error_type": record.error_type.value if record.error_type else "unknown_error",
                        "is_retryable": record.is_retryable,
                        "latency_ms": record.latency_ms,
                    })
                    act_detail = (
                        f"Tool {record.tool_name} FAILED "
                        f"({record.error_type.value if record.error_type else 'unknown'}, "
                        f"retryable={record.is_retryable}) "
                        f"in {record.latency_ms:.0f}ms: {record.error}"
                    )

                    if self.failure_policy == FailurePolicy.FAIL_FAST:
                        self._log_react_step(
                            step=ReActStep.ACT,
                            iteration=iter_num,
                            detail=act_detail,
                            latency_ms=act_latency,
                            metadata={
                                "tool_name": record.tool_name,
                                "success": False,
                                "failure_policy": self.failure_policy.value,
                                "error_type": record.error_type.value if record.error_type else "unknown_error",
                            },
                        )
                        raise ToolOrchestrationError(
                            f"Tool {record.tool_name} failed: {record.error}"
                        )

                    elif self.failure_policy == FailurePolicy.RETRY:
                        if record.is_retryable:
                            logger.info(
                                "Retrying tool %s (policy=retry, error_type=%s)",
                                record.tool_name,
                                record.error_type.value if record.error_type else "unknown",
                                extra={"user_id": user_id},
                            )
                            retry_record = await self._execute_single_tool(
                                tool_call=tool_call,
                                user_id=user_id,
                                iteration=iter_num,
                            )
                            self._invocation_log.append(retry_record)
                            if retry_record.success:
                                tool_calls_made += 1
                                tool_results[-1] = {
                                    "tool_name": retry_record.tool_name,
                                    "result": retry_record.result,
                                    "latency_ms": retry_record.latency_ms,
                                }
                                act_detail = (
                                    f"Retried {retry_record.tool_name} successfully "
                                    f"in {retry_record.latency_ms:.0f}ms"
                                )
                                record = retry_record
                            else:
                                act_detail = (
                                    f"Tool {record.tool_name} FAILED after retry: "
                                    f"{retry_record.error}"
                                )
                                record = retry_record
                        else:
                            logger.info(
                                "Skipping retry for %s (not retryable, error_type=%s)",
                                record.tool_name,
                                record.error_type.value if record.error_type else "unknown",
                                extra={"user_id": user_id},
                            )

                    # SKIP: fall through, error already in tool_results

                self._log_react_step(
                    step=ReActStep.ACT,
                    iteration=iter_num,
                    detail=act_detail,
                    latency_ms=act_latency,
                    metadata={
                        "tool_name": record.tool_name,
                        "parameters": record.parameters,
                        "success": record.success,
                        "error_type": record.error_type.value if record.error_type else None,
                        "is_retryable": record.is_retryable if not record.success else None,
                    },
                )

                # ── OBSERVE: append tool result to conversation ─────
                # For errors, provide structured info so the LLM can
                # decide whether to retry with different params or give up.
                if record.success:
                    result_content = json.dumps(record.result)
                else:
                    error_payload: Dict[str, Any] = {
                        "success": False,
                        "error": record.error,
                        "error_type": record.error_type.value if record.error_type else "unknown_error",
                        "is_retryable": record.is_retryable,
                    }
                    result_content = json.dumps(error_payload)
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": record.tool_name,
                    "content": result_content,
                })

                result_preview = (
                    result_content[:120] + "…"
                    if len(result_content) > 120
                    else result_content
                )
                observe_detail = (
                    f"Tool {record.tool_name} result appended to conversation "
                    f"(success={record.success}, preview={result_preview})"
                )
                self._log_react_step(
                    step=ReActStep.OBSERVE,
                    iteration=iter_num,
                    detail=observe_detail,
                    latency_ms=0.0,
                    metadata={
                        "tool_name": record.tool_name,
                        "result_length": len(result_content),
                        "success": record.success,
                    },
                )

        # ── Iteration limit reached ────────────────────────────────
        logger.warning(
            "Max tool iterations reached (%d), %d tool call(s) made",
            self.max_iterations,
            tool_calls_made,
            extra={"user_id": user_id, "tool_calls_made": tool_calls_made},
        )
        self._log_debug_summary(
            user_id=user_id,
            iterations=self.max_iterations,
            tool_calls_made=tool_calls_made,
            orchestration_start=orchestration_start,
            max_reached=True,
        )
        return self._build_result(
            content=(
                "I apologize, but I need to simplify my approach. "
                "Could you rephrase your request?"
            ),
            tool_calls_made=tool_calls_made,
            iterations=self.max_iterations,
            tool_results=tool_results,
            max_iterations_reached=True,
            model_used="unknown",
        )

    @property
    def invocation_log(self) -> List[ToolInvocationRecord]:
        """Return the invocation log from the most recent orchestration."""
        return list(self._invocation_log)

    @property
    def react_log(self) -> List[ReActStepRecord]:
        """Return the ReAct step log from the most recent orchestration."""
        return list(self._react_log)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _log_react_step(
        self,
        step: ReActStep,
        iteration: int,
        detail: str,
        latency_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a ReAct step and emit a structured log message."""
        record = ReActStepRecord(
            step=step,
            iteration=iteration,
            detail=detail,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )
        self._react_log.append(record)
        logger.debug(
            "[%s] iter=%d | %s (%.0fms)",
            step.value.upper(),
            iteration,
            detail,
            latency_ms,
            extra={
                "react_step": step.value,
                "iteration": iteration,
                "latency_ms": latency_ms,
                **(metadata or {}),
            },
        )

    def _log_debug_summary(
        self,
        user_id: int,
        iterations: int,
        tool_calls_made: int,
        orchestration_start: float,
        max_reached: bool,
    ) -> None:
        """Emit a single debug summary of the entire orchestration run."""
        total_ms = (time.time() - orchestration_start) * 1000
        think_steps = [r for r in self._react_log if r.step == ReActStep.THINK]
        act_steps = [r for r in self._react_log if r.step == ReActStep.ACT]
        observe_steps = [r for r in self._react_log if r.step == ReActStep.OBSERVE]

        summary = (
            f"ReAct summary: {iterations} iteration(s), "
            f"{tool_calls_made} tool call(s), "
            f"{len(think_steps)} think / {len(act_steps)} act / "
            f"{len(observe_steps)} observe steps, "
            f"total={total_ms:.0f}ms, max_reached={max_reached}"
        )
        logger.info(
            summary,
            extra={
                "user_id": user_id,
                "iterations": iterations,
                "tool_calls_made": tool_calls_made,
                "total_latency_ms": total_ms,
                "max_iterations_reached": max_reached,
                "think_steps": len(think_steps),
                "act_steps": len(act_steps),
                "observe_steps": len(observe_steps),
            },
        )

    async def _execute_single_tool(
        self,
        tool_call: Dict[str, Any],
        user_id: int,
        iteration: int,
    ) -> ToolInvocationRecord:
        """Execute one tool call with granular error handling and logging.

        Wraps the tool execution in a try-catch that classifies errors by
        type (timeout, permission, validation, etc.) and produces structured
        :class:`ToolFailureDetail` records for observability.  The error
        information is formatted so the LLM can see *what* went wrong and
        decide whether to retry with different parameters.
        """
        tool_name = tool_call["function"]["name"]
        try:
            arguments = json.loads(tool_call["function"]["arguments"])
        except (json.JSONDecodeError, KeyError):
            arguments = {}

        logger.info(
            "Executing tool: %s (iteration %d, user_id=%d)",
            tool_name,
            iteration,
            user_id,
            extra={
                "user_id": user_id,
                "tool_name": tool_name,
                "parameters": arguments,
                "iteration": iteration,
            },
        )

        start = time.time()
        try:
            result = await execute_tool(
                tool_name=tool_name,
                parameters=arguments,
                user_id=user_id,
                db=self.db,
            )
            latency_ms = (time.time() - start) * 1000

            logger.info(
                "Tool %s succeeded in %.0f ms (user_id=%d)",
                tool_name,
                latency_ms,
                user_id,
                extra={"user_id": user_id, "tool_name": tool_name},
            )
            return ToolInvocationRecord(
                tool_name=tool_name,
                parameters=arguments,
                result=result,
                latency_ms=latency_ms,
                iteration=iteration,
                success=True,
                user_id=user_id,
            )

        except TimeoutError as exc:
            return self._handle_tool_error(
                exc, ToolErrorType.TIMEOUT_ERROR, True,
                tool_name, arguments, start, iteration, user_id,
            )
        except PermissionError as exc:
            return self._handle_tool_error(
                exc, ToolErrorType.PERMISSION_ERROR, False,
                tool_name, arguments, start, iteration, user_id,
            )
        except (FileNotFoundError, KeyError, LookupError) as exc:
            return self._handle_tool_error(
                exc, ToolErrorType.NOT_FOUND_ERROR, False,
                tool_name, arguments, start, iteration, user_id,
            )
        except ConnectionError as exc:
            return self._handle_tool_error(
                exc, ToolErrorType.CONNECTION_ERROR, True,
                tool_name, arguments, start, iteration, user_id,
            )
        except (ValueError, TypeError) as exc:
            return self._handle_tool_error(
                exc, ToolErrorType.VALIDATION_ERROR, False,
                tool_name, arguments, start, iteration, user_id,
            )
        except Exception as exc:
            return self._handle_tool_error(
                exc, ToolErrorType.RUNTIME_ERROR, False,
                tool_name, arguments, start, iteration, user_id,
            )

    def _handle_tool_error(
        self,
        exc: Exception,
        error_type: ToolErrorType,
        is_retryable: bool,
        tool_name: str,
        arguments: Dict[str, Any],
        start: float,
        iteration: int,
        user_id: int,
    ) -> ToolInvocationRecord:
        """Build a :class:`ToolInvocationRecord` and :class:`ToolFailureDetail`
        from a caught exception, then log the failure with full context."""
        latency_ms = (time.time() - start) * 1000
        tb_summary = traceback.format_exception_only(type(exc), exc)
        tb_lines = "".join(tb_summary).strip()

        failure = ToolFailureDetail(
            tool_name=tool_name,
            error_type=error_type,
            error_message=str(exc),
            is_retryable=is_retryable,
            iteration=iteration,
            user_id=user_id,
            parameters=arguments,
            traceback_summary=tb_lines,
        )

        logger.error(
            "Tool %s failed in %.0f ms (user_id=%d, error_type=%s, retryable=%s): %s",
            tool_name,
            latency_ms,
            user_id,
            error_type.value,
            is_retryable,
            exc,
            extra={
                "user_id": user_id,
                "tool_name": tool_name,
                "error_type": error_type.value,
                "is_retryable": is_retryable,
                "parameters": arguments,
                "iteration": iteration,
                "traceback_summary": tb_lines,
            },
            exc_info=True,
        )

        return ToolInvocationRecord(
            tool_name=tool_name,
            parameters=arguments,
            error=str(exc),
            latency_ms=latency_ms,
            iteration=iteration,
            success=False,
            user_id=user_id,
            error_type=error_type,
            is_retryable=is_retryable,
            failure_detail=failure,
        )

    @staticmethod
    def _coerce_tool_params(
        arguments: Dict[str, Any],
        tool_schemas: Dict[str, Dict[str, Any]],
        tool_name: str,
    ) -> Dict[str, Any]:
        """Coerce string-encoded parameters to the type declared in the schema.

        Small LLMs frequently double-encode structured parameters (arrays,
        objects) as JSON strings, or emit numeric values as strings.  This
        step normalises them before validation so a fixable format issue does
        not consume a retry iteration.
        """
        schema = tool_schemas.get(tool_name)
        if not schema:
            return arguments

        properties = schema.get("properties", {})
        coerced = dict(arguments)

        for param_name, param_value in arguments.items():
            prop_schema = properties.get(param_name)
            if not prop_schema or not isinstance(param_value, str):
                continue
            expected_type = prop_schema.get("type")
            if expected_type in ("array", "object"):
                try:
                    coerced[param_name] = json.loads(param_value)
                except (json.JSONDecodeError, ValueError):
                    pass
            elif expected_type == "integer":
                try:
                    coerced[param_name] = int(param_value)
                except (ValueError, TypeError):
                    pass
            elif expected_type == "number":
                try:
                    coerced[param_name] = float(param_value)
                except (ValueError, TypeError):
                    pass

        return coerced

    @staticmethod
    def _validate_tool_params(
        tool_name: str,
        arguments: Dict[str, Any],
        tool_schemas: Dict[str, Dict[str, Any]],
    ) -> Optional[str]:
        """Validate tool parameters against the schema from tool_definitions.

        Returns an error message string if validation fails, or ``None`` if
        the parameters are acceptable.
        """
        schema = tool_schemas.get(tool_name)
        if schema is None:
            # No schema available → skip validation (tool may still be valid)
            return None

        required: List[str] = schema.get("required", [])
        properties: Dict[str, Any] = schema.get("properties", {})

        # Check required parameters are present
        missing = [p for p in required if p not in arguments]
        if missing:
            return f"Missing required parameter(s): {', '.join(missing)}"

        # Check for unknown parameters
        if properties:
            unknown = [k for k in arguments if k not in properties]
            if unknown:
                return f"Unknown parameter(s): {', '.join(unknown)}"

        # Basic type checking against declared types
        _JSON_TYPE_MAP = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for param_name, param_value in arguments.items():
            prop_schema = properties.get(param_name)
            if not prop_schema:
                continue
            expected_type_str = prop_schema.get("type")
            if not expected_type_str:
                continue
            expected_type = _JSON_TYPE_MAP.get(expected_type_str)
            if expected_type and not isinstance(param_value, expected_type):
                return (
                    f"Parameter '{param_name}' expected type "
                    f"'{expected_type_str}', got '{type(param_value).__name__}'"
                )

            # Enum validation
            enum_values = prop_schema.get("enum")
            if enum_values and param_value not in enum_values:
                return (
                    f"Parameter '{param_name}' value '{param_value}' "
                    f"not in allowed values: {enum_values}"
                )

        return None

    @staticmethod
    def _build_result(
        content: str,
        tool_calls_made: int,
        iterations: int,
        tool_results: List[Dict[str, Any]],
        max_iterations_reached: bool,
        model_used: str,
    ) -> Dict[str, Any]:
        """Build the standardised result dict."""
        return {
            "content": content,
            "tool_calls_made": tool_calls_made,
            "iterations": iterations,
            "tool_results": tool_results,
            "max_iterations_reached": max_iterations_reached,
            "model_used": model_used,
            "response_token_count": 0,
            "intent": "general",
            "evidence_cards": [],
        }
