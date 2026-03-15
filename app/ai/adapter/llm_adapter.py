"""
LLM Provider Adapter Interface

This module defines the abstract interface for LLM provider adapters,
enabling model-agnostic invocation with structured output contracts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Type, Generator, Optional, Dict, Any
from pydantic import BaseModel

from app.ai.context.builder import Context


@dataclass
class LLMConfig:
    """Configuration for LLM invocation"""
    model_name: str
    temperature: float
    max_tokens: int
    top_p: float


@dataclass
class LLMResponse:
    """Response from LLM invocation with metadata"""
    parsed_output: BaseModel  # The validated output contract instance
    model_used: str  # Which model was actually used
    token_count: int  # Total tokens used
    latency_ms: int  # Response time in milliseconds


@dataclass
class StreamChunk:
    """A single chunk emitted during streaming.

    Attributes:
        content: Text fragment (empty string for non-content chunks).
        chunk_type: One of ``"content"``, ``"tool_call"``, ``"error"``, ``"done"``.
        tool_call: Tool-call payload when ``chunk_type == "tool_call"``.
        error: Error message when ``chunk_type == "error"``.
        metadata: Final metadata dict emitted with the ``"done"`` chunk.
    """
    content: str = ""
    chunk_type: str = "content"  # content | tool_call | error | done
    tool_call: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMProviderAdapter(ABC):
    """Abstract base class for LLM provider adapters"""

    @abstractmethod
    def invoke(self, context: Context, contract: Type[BaseModel]) -> LLMResponse:
        """
        Invoke the LLM with the given context and output contract.

        Args:
            context: The structured context containing all prompt layers
            contract: The Pydantic model class defining the expected output schema

        Returns:
            LLMResponse containing the parsed output and invocation metadata

        Raises:
            Exception: If invocation fails or output validation fails
        """
        pass

    @abstractmethod
    def stream(
        self,
        context: Context,
        operation_type: str = "unknown",
        athlete_id: Optional[int] = None,
    ) -> Generator[StreamChunk, None, None]:
        """Stream LLM response as incremental chunks.

        Yields ``StreamChunk`` objects.  The final chunk has
        ``chunk_type="done"`` and carries aggregated metadata (model used,
        token counts, latency).  If a tool call is detected mid-stream the
        chunk will have ``chunk_type="tool_call"`` with the parsed payload.

        Errors are yielded as ``chunk_type="error"`` chunks rather than
        raised, so the caller's event loop is never broken.

        Args:
            context: Structured context with all prompt layers.
            operation_type: Telemetry label (e.g. ``"chat_response"``).
            athlete_id: Athlete ID for telemetry scoping.

        Yields:
            ``StreamChunk`` instances.
        """
        pass
