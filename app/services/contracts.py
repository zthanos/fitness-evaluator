"""ChatAgent ↔ ChatSessionService interface contracts.

This module formalises the data shapes that flow between
ChatMessageHandler, ChatSessionService, and ChatAgent so that each
component can be developed, tested, and replaced independently.

Contracts defined here:
- ``ConversationTurn``  – single message in a conversation history
- ``AgentInput``        – everything ChatAgent.execute() needs
- ``AgentResult``       – everything ChatAgent.execute() returns
- ``AgentError``        – structured error envelope

Design reference: Phase 3 – Introduce ChatAgent (design.md §ChatAgent Interface)
Requirements:  3.1 Runtime Execution Owner, 3.2 Clean Orchestration Boundaries
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Input contract
# ---------------------------------------------------------------------------


class MessageRole(str, Enum):
    """Allowed roles inside a conversation turn.

    Mirrors the CHECK constraint on ``chat_messages.role``.
    """

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ConversationTurn:
    """A single message exchanged in a chat session.

    This is the canonical shape that ChatSessionService returns from
    ``get_active_buffer()`` and that ChatAgent receives as
    ``conversation_history``.

    Attributes:
        role: Who produced the message (``"user"`` or ``"assistant"``).
        content: The message body (plain text).
        created_at: UTC timestamp of when the message was created.
            ``None`` for messages that have not been persisted yet.

    Example::

        turn = ConversationTurn(
            role=MessageRole.USER,
            content="How was my long run last Sunday?",
            created_at=datetime(2025, 6, 10, 8, 30),
        )
    """

    role: MessageRole
    content: str
    created_at: Optional[datetime] = None

    # Convenience helpers ------------------------------------------------

    def to_dict(self) -> Dict[str, str]:
        """Serialise to the ``{"role": …, "content": …}`` dict that LLM
        adapters expect.

        Example::

            >>> turn.to_dict()
            {'role': 'user', 'content': 'How was my long run last Sunday?'}
        """
        return {"role": self.role.value, "content": self.content}

    @classmethod
    def from_chat_message(cls, msg: Any) -> "ConversationTurn":
        """Build a ``ConversationTurn`` from an ORM ``ChatMessage`` instance.

        Args:
            msg: A ``ChatMessage`` ORM object with ``.role``, ``.content``,
                and ``.created_at`` attributes.

        Example::

            turns = [
                ConversationTurn.from_chat_message(m)
                for m in session_service.get_active_buffer(session_id)
            ]
        """
        return cls(
            role=MessageRole(msg.role),
            content=msg.content,
            created_at=getattr(msg, "created_at", None),
        )


@dataclass(frozen=True)
class AgentInput:
    """Everything ``ChatAgent.execute()`` requires from the handler.

    The handler builds this from ChatSessionService data and the incoming
    API request, then passes it to the agent.  This decouples the agent
    from HTTP/session concerns.

    Attributes:
        user_message: The athlete's current query text.
        session_id: Numeric chat-session identifier.
        user_id: Numeric athlete / user identifier.
        conversation_history: Ordered list of prior turns in the session
            (oldest first).  Obtained via
            ``ChatSessionService.get_active_buffer()``.

    Example::

        agent_input = AgentInput(
            user_message="What should my tempo pace be?",
            session_id=42,
            user_id=7,
            conversation_history=[
                ConversationTurn(
                    role=MessageRole.USER,
                    content="I ran 10 km yesterday",
                ),
                ConversationTurn(
                    role=MessageRole.ASSISTANT,
                    content="Nice work! How did it feel?",
                ),
            ],
        )
    """

    user_message: str
    session_id: int
    user_id: int
    conversation_history: List[ConversationTurn] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Structured response returned by ``ChatAgent.execute()``.

    The handler uses this to persist the assistant message via
    ``ChatSessionService.append_messages()`` and to build the API
    response payload.

    Attributes:
        content: Final assistant response text.
        tool_calls_made: Number of tool invocations during execution.
        iterations: Number of tool-loop iterations completed.
        latency_ms: Wall-clock execution time in milliseconds.
        model_used: Identifier of the model that produced the response
            (e.g. ``"mixtral:8x7b-instruct"``).
        context_token_count: Approximate token count of the assembled
            context sent to the model.
        response_token_count: Approximate token count of the model's
            response.
        intent: Classified intent label (e.g. ``"recent_performance"``).
        evidence_cards: Evidence cards attached to the response.

    Example::

        result = AgentResult(
            content="Your tempo pace should be around 5:15/km based on ...",
            tool_calls_made=1,
            iterations=1,
            latency_ms=1420.5,
            model_used="mixtral:8x7b-instruct",
            context_token_count=1800,
            response_token_count=210,
            intent="training_plan",
            evidence_cards=[{"source_id": "act-123", "summary": "10 km run"}],
        )
    """

    content: str
    tool_calls_made: int = 0
    iterations: int = 0
    latency_ms: float = 0.0
    model_used: str = "unknown"
    context_token_count: int = 0
    response_token_count: int = 0
    intent: str = "general"
    evidence_cards: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict suitable for JSON API responses.

        Example::

            >>> result.to_dict()
            {'content': '...', 'tool_calls_made': 1, ...}
        """
        return {
            "content": self.content,
            "tool_calls_made": self.tool_calls_made,
            "iterations": self.iterations,
            "latency_ms": self.latency_ms,
            "model_used": self.model_used,
            "context_token_count": self.context_token_count,
            "response_token_count": self.response_token_count,
            "intent": self.intent,
            "evidence_cards": self.evidence_cards,
        }


# ---------------------------------------------------------------------------
# Error handling contract
# ---------------------------------------------------------------------------


class AgentErrorKind(str, Enum):
    """Categorisation of errors that ``ChatAgent`` may raise.

    The handler inspects ``AgentError.kind`` to decide whether to retry,
    return a user-friendly message, or escalate.

    Members:
        CONTEXT_BUILD_FAILURE: ChatContextBuilder could not assemble context
            (e.g. missing prompts, DB unreachable).
        LLM_INVOCATION_FAILURE: The LLM call failed after exhausting
            primary + fallback models.
        TOOL_EXECUTION_FAILURE: One or more tool calls failed and the
            agent could not recover.
        MAX_ITERATIONS_REACHED: The tool-calling loop hit its iteration
            cap without producing a final answer.
        UNKNOWN: Catch-all for unexpected errors.
    """

    CONTEXT_BUILD_FAILURE = "context_build_failure"
    LLM_INVOCATION_FAILURE = "llm_invocation_failure"
    TOOL_EXECUTION_FAILURE = "tool_execution_failure"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AgentError:
    """Structured error envelope returned or raised by ChatAgent.

    Rather than leaking raw exceptions across the boundary, the agent
    wraps failures in this envelope so the handler can react uniformly.

    Attributes:
        kind: High-level error category.
        message: Human-readable description of what went wrong.
        details: Optional dict with debugging context (stack trace
            excerpt, model name, iteration count, etc.).
        retryable: Hint to the caller on whether a retry is sensible.

    Example::

        error = AgentError(
            kind=AgentErrorKind.LLM_INVOCATION_FAILURE,
            message="Primary and fallback models both timed out.",
            details={"primary": "mixtral:8x7b-instruct", "fallback": "llama3.1:8b-instruct"},
            retryable=True,
        )
    """

    kind: AgentErrorKind
    message: str
    details: Optional[Dict[str, Any]] = None
    retryable: bool = False
