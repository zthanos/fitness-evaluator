"""
LangChain Adapter Implementation

This module provides a LangChain-based implementation of the LLMProviderAdapter
interface, supporting Mixtral and Llama models via ChatOllama/ChatOpenAI with structured output.
"""

import json
import time
import logging
from typing import Type, Optional, Generator, Dict, Any
from datetime import datetime
import tiktoken
from pydantic import BaseModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
import requests.exceptions

from app.ai.adapter.llm_adapter import LLMProviderAdapter, LLMResponse, StreamChunk
from app.ai.context.builder import Context
from app.ai.telemetry.invocation_logger import InvocationLogger, InvocationLog
from app.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)


class LangChainAdapter(LLMProviderAdapter):
    """LangChain-based LLM adapter with Mixtral primary and Llama fallback"""

    def __init__(
        self,
        primary_model: str = "mixtral:8x7b-instruct",
        fallback_model: str = "llama3.1:8b-instruct",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2000,
        invocation_logger: Optional[InvocationLogger] = None
    ):
        """
        Initialize the LangChain adapter.

        Args:
            primary_model: Primary model name (default: Mixtral-8x7B-Instruct)
            fallback_model: Fallback model name (default: Llama-3.1-8B-Instruct)
            base_url: Ollama base URL (default: http://localhost:11434)
            temperature: Sampling temperature (default: 0.7)
            top_p: Nucleus sampling parameter (default: 0.9)
            max_tokens: Maximum tokens to generate (default: 2000)
            invocation_logger: Optional InvocationLogger instance (creates default if None)
        """
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.base_url = base_url
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.invocation_logger = invocation_logger or InvocationLogger()

    def invoke(
        self,
        context: Context,
        contract: Type[BaseModel],
        operation_type: str = "unknown",
        athlete_id: Optional[int] = None
    ) -> LLMResponse:
        """
        Invoke the LLM with structured output enforcement and automatic fallback.

        Tries the primary model (Mixtral) first. If it fails with a timeout or
        connection error, automatically retries with the fallback model (Llama).

        Logs invocation telemetry including token counts, latency, model used,
        and success/failure status.

        Args:
            context: The structured context containing all prompt layers
            contract: The Pydantic model class defining the expected output schema
            operation_type: Type of operation (e.g., 'weekly_eval', 'chat_response')
            athlete_id: ID of the athlete for whom the operation is performed

        Returns:
            LLMResponse containing the parsed output and invocation metadata

        Raises:
            Exception: If both primary and fallback models fail
        """
        # Start timing (includes retry time)
        start_time = time.time()

        # Convert context to messages
        messages = context.to_messages()

        # Track model and fallback state for telemetry
        model_used = None
        parsed_output = None
        response_token_count = 0
        fallback_used = False

        try:
            # Try primary model first
            model_start = time.time()
            try:
                logger.info(f"Invoking primary model: {self.primary_model}")
                parsed_output = self._invoke_model(self.primary_model, messages, contract)
                model_used = self.primary_model
                logger.info(f"Successfully invoked primary model: {self.primary_model}")
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Log the primary model failure
                logger.warning(
                    f"Primary model {self.primary_model} failed with {type(e).__name__}: {str(e)}. "
                    f"Retrying with fallback model: {self.fallback_model}"
                )

                # Retry with fallback model
                try:
                    fallback_used = True
                    parsed_output = self._invoke_model(self.fallback_model, messages, contract)
                    model_used = self.fallback_model
                    logger.info(f"Successfully invoked fallback model: {self.fallback_model}")
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback model {self.fallback_model} also failed: {type(fallback_error).__name__}: {str(fallback_error)}"
                    )
                    raise fallback_error
            except Exception as e:
                # Check if error message contains "connection" or "timeout"
                error_msg = str(e).lower()
                if "connection" in error_msg or "timeout" in error_msg:
                    logger.warning(
                        f"Primary model {self.primary_model} failed with connection/timeout error: {str(e)}. "
                        f"Retrying with fallback model: {self.fallback_model}"
                    )

                    # Retry with fallback model
                    try:
                        fallback_used = True
                        parsed_output = self._invoke_model(self.fallback_model, messages, contract)
                        model_used = self.fallback_model
                        logger.info(f"Successfully invoked fallback model: {self.fallback_model}")
                    except Exception as fallback_error:
                        logger.error(
                            f"Fallback model {self.fallback_model} also failed: {type(fallback_error).__name__}: {str(fallback_error)}"
                        )
                        raise fallback_error
                else:
                    # Not a connection/timeout error, re-raise immediately
                    logger.error(f"Primary model {self.primary_model} failed with non-retryable error: {type(e).__name__}: {str(e)}")
                    raise

            model_latency_ms = (time.time() - model_start) * 1000

            # Calculate latency (includes retry time if fallback was used)
            latency_ms = int((time.time() - start_time) * 1000)

            # Count response tokens
            response_token_count = self._count_response_tokens(parsed_output)

            # Log successful invocation with full telemetry
            self._log_invocation(
                operation_type=operation_type,
                athlete_id=athlete_id,
                model_used=model_used,
                context_token_count=context.token_count,
                response_token_count=response_token_count,
                latency_ms=latency_ms,
                success=True,
                error_message=None,
                model_latency_ms=model_latency_ms,
                total_latency_ms=latency_ms,
                fallback_used=fallback_used,
            )
            self._persist_llm_call(
                source=operation_type or "chat_invoke",
                model=model_used or self.primary_model,
                messages=messages,
                response_content=parsed_output.model_dump_json() if parsed_output else None,
                duration_ms=latency_ms,
            )

            return LLMResponse(
                parsed_output=parsed_output,
                model_used=model_used,
                token_count=context.token_count + response_token_count,
                latency_ms=latency_ms
            )

        except Exception as e:
            # Calculate latency even for failures
            latency_ms = int((time.time() - start_time) * 1000)

            # Log failed invocation
            self._log_invocation(
                operation_type=operation_type,
                athlete_id=athlete_id,
                model_used=model_used or self.primary_model,
                context_token_count=context.token_count,
                response_token_count=0,
                latency_ms=latency_ms,
                success=False,
                error_message=f"{type(e).__name__}: {str(e)}",
                fallback_used=fallback_used,
            )
            self._persist_llm_call(
                source=operation_type or "chat_invoke",
                model=model_used or self.primary_model,
                messages=messages,
                response_content=None,
                duration_ms=latency_ms,
                error=f"{type(e).__name__}: {str(e)}",
            )

            # Re-raise the exception
            raise

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def stream(
        self,
        context: Context,
        operation_type: str = "unknown",
        athlete_id: Optional[int] = None,
    ) -> Generator[StreamChunk, None, None]:
        """Stream LLM response as incremental ``StreamChunk`` objects.

        Tries the primary model first; on timeout / connection errors it
        transparently retries with the fallback model.  Tool-call chunks
        are detected from ``AIMessageChunk.tool_call_chunks`` and yielded
        with ``chunk_type="tool_call"``.  Errors are yielded as
        ``chunk_type="error"`` so the caller's event loop is never broken.

        A final ``chunk_type="done"`` chunk carries aggregated metadata
        (model used, token counts, latency).  Telemetry is emitted to
        ``InvocationLogger`` after the stream completes regardless of
        success or failure.
        """
        start_time = time.time()
        messages = context.to_messages()
        model_used = self.primary_model
        # Mutable containers so _stream_from_model can update them
        content_parts: list[str] = []
        tool_calls_collected: list[Dict[str, Any]] = []
        success = False
        error_message: Optional[str] = None
        fallback_used = False
        model_start = time.time()

        try:
            try:
                yield from self._stream_from_model(
                    self.primary_model, messages,
                    content_parts, tool_calls_collected,
                )
                model_used = self.primary_model
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as primary_err:
                logger.warning(
                    "Primary model %s stream failed (%s), retrying with %s",
                    self.primary_model, primary_err, self.fallback_model,
                )
                content_parts.clear()
                tool_calls_collected.clear()
                try:
                    yield from self._stream_from_model(
                        self.fallback_model, messages,
                        content_parts, tool_calls_collected,
                    )
                    model_used = self.fallback_model
                    fallback_used = True
                except Exception as fallback_err:
                    error_message = f"{type(fallback_err).__name__}: {fallback_err}"
                    yield StreamChunk(chunk_type="error", error=error_message)
                    return
            except Exception as primary_err:
                err_lower = str(primary_err).lower()
                if "connection" in err_lower or "timeout" in err_lower:
                    logger.warning(
                        "Primary model %s stream failed (%s), retrying with %s",
                        self.primary_model, primary_err, self.fallback_model,
                    )
                    content_parts.clear()
                    tool_calls_collected.clear()
                    try:
                        yield from self._stream_from_model(
                            self.fallback_model, messages,
                            content_parts, tool_calls_collected,
                        )
                        model_used = self.fallback_model
                        fallback_used = True
                    except Exception as fallback_err:
                        error_message = f"{type(fallback_err).__name__}: {fallback_err}"
                        yield StreamChunk(chunk_type="error", error=error_message)
                        return
                else:
                    error_message = f"{type(primary_err).__name__}: {primary_err}"
                    yield StreamChunk(chunk_type="error", error=error_message)
                    return

            success = True

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            yield StreamChunk(chunk_type="error", error=error_message)

        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            model_latency_ms = (time.time() - model_start) * 1000
            full_text = "".join(content_parts)
            response_token_count = (
                len(self.encoding.encode(full_text)) if full_text else 0
            )

            # Emit telemetry
            self._log_invocation(
                operation_type=operation_type,
                athlete_id=athlete_id,
                model_used=model_used,
                context_token_count=context.token_count,
                response_token_count=response_token_count,
                latency_ms=latency_ms,
                success=success,
                error_message=error_message,
                model_latency_ms=model_latency_ms,
                total_latency_ms=latency_ms,
                fallback_used=fallback_used,
            )
            self._persist_llm_call(
                source=operation_type or "chat_stream",
                model=model_used,
                messages=messages,
                response_content=full_text or None,
                duration_ms=latency_ms,
                tool_calls=tool_calls_collected or None,
                error=error_message,
            )

            # Yield the terminal "done" chunk with metadata
            yield StreamChunk(
                chunk_type="done",
                metadata={
                    "model_used": model_used,
                    "context_token_count": context.token_count,
                    "response_token_count": response_token_count,
                    "latency_ms": latency_ms,
                    "model_latency_ms": model_latency_ms,
                    "fallback_used": fallback_used,
                    "success": success,
                    "tool_calls": tool_calls_collected,
                },
            )

    def _stream_from_model(
        self,
        model_name: str,
        messages: list,
        content_parts: list[str],
        tool_calls_collected: list,
    ) -> Generator[StreamChunk, None, None]:
        """Yield ``StreamChunk`` objects from a single model's stream.

        Appends text fragments to *content_parts* (mutable list) so the
        caller can compute the final token count.  Tool-call fragments
        are accumulated across chunks and yielded as complete
        ``tool_call`` chunks once the stream finishes.
        """
        settings = get_settings()

        if settings.LLM_TYPE.lower() in ("lm-studio", "openai"):
            base_url = self.base_url
            if not base_url.endswith("/v1"):
                base_url = f"{base_url}/v1"
            llm = ChatOpenAI(
                base_url=base_url,
                api_key="lm-studio",
                model=model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                streaming=True,
            )
        else:
            llm = ChatOllama(
                model=model_name,
                base_url=self.base_url,
                temperature=self.temperature,
                top_p=self.top_p,
                num_predict=self.max_tokens,
            )

        # Build LangChain message objects
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        # Partial tool-call accumulator: index → {name, args_json}
        partial_tool_calls: Dict[int, Dict[str, str]] = {}

        for chunk in llm.stream(lc_messages):
            # --- Content tokens ---
            text = ""
            if isinstance(chunk, AIMessageChunk):
                text = chunk.content or ""
            elif hasattr(chunk, "content"):
                text = chunk.content or ""

            if text:
                content_parts.append(text)
                yield StreamChunk(content=text, chunk_type="content")

            # --- Tool-call fragments ---
            tc_chunks = getattr(chunk, "tool_call_chunks", None) or []
            for tc in tc_chunks:
                idx = tc.get("index", 0)
                if idx not in partial_tool_calls:
                    partial_tool_calls[idx] = {"name": "", "args": ""}
                if tc.get("name"):
                    partial_tool_calls[idx]["name"] += tc["name"]
                if tc.get("args"):
                    partial_tool_calls[idx]["args"] += tc["args"]

        # Flush any accumulated tool calls
        for _idx, tc_data in sorted(partial_tool_calls.items()):
            args_parsed: Any = tc_data["args"]
            try:
                args_parsed = json.loads(tc_data["args"]) if tc_data["args"] else {}
            except json.JSONDecodeError:
                pass  # keep raw string
            tool_call_payload = {
                "name": tc_data["name"],
                "arguments": args_parsed,
            }
            tool_calls_collected.append(tool_call_payload)
            yield StreamChunk(
                chunk_type="tool_call",
                tool_call=tool_call_payload,
            )

    def _invoke_model(self, model_name: str, messages: list, contract: Type[BaseModel]) -> BaseModel:
        """
        Invoke a specific model with structured output.

        Args:
            model_name: The model to invoke
            messages: The messages to send to the model
            contract: The Pydantic model class defining the expected output schema

        Returns:
            The parsed output conforming to the contract

        Raises:
            Exception: If invocation fails
        """
        settings = get_settings()

        # Determine which LLM client to use based on LLM_TYPE
        if settings.LLM_TYPE.lower() in ["lm-studio", "openai"]:
            # Use ChatOpenAI for LM Studio and OpenAI
            base_url = self.base_url
            # Ensure /v1 is in the URL for OpenAI-compatible endpoints
            if not base_url.endswith('/v1'):
                base_url = f"{base_url}/v1"

            llm = ChatOpenAI(
                base_url=base_url,
                api_key="lm-studio",  # LM Studio doesn't require a real key
                model=model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
        else:
            # Use ChatOllama for Ollama
            llm = ChatOllama(
                model=model_name,
                base_url=self.base_url,
                temperature=self.temperature,
                top_p=self.top_p,
                num_predict=self.max_tokens
            )

        # Use with_structured_output for schema enforcement
        structured_llm = llm.with_structured_output(contract)

        # Invoke the LLM
        return structured_llm.invoke(messages)

    def _count_response_tokens(self, response: BaseModel) -> int:
        """
        Count tokens in the response using tiktoken.

        Args:
            response: The parsed Pydantic model response

        Returns:
            Approximate token count for the response
        """
        # Convert response to JSON string and count tokens
        response_text = response.model_dump_json()
        return len(self.encoding.encode(response_text))

    def _log_invocation(
        self,
        operation_type: str,
        athlete_id: Optional[int],
        model_used: str,
        context_token_count: int,
        response_token_count: int,
        latency_ms: float,
        success: bool,
        error_message: Optional[str],
        retrieval_latency_ms: Optional[float] = None,
        model_latency_ms: Optional[float] = None,
        total_latency_ms: Optional[float] = None,
        fallback_used: Optional[bool] = None,
    ) -> None:
        """
        Log an invocation to the telemetry system.

        Args:
            operation_type: Type of operation (e.g., 'weekly_eval', 'chat_response')
            athlete_id: ID of the athlete for whom the operation was performed
            model_used: Name of the LLM model used
            context_token_count: Number of tokens in the input context
            response_token_count: Number of tokens in the LLM response
            latency_ms: Time taken from context build to response parse (milliseconds)
            success: Whether the invocation succeeded
            error_message: Error details if success is False, None otherwise
            retrieval_latency_ms: Time spent on RAG/context retrieval (milliseconds)
            model_latency_ms: Time spent on LLM model invocation (milliseconds)
            total_latency_ms: End-to-end latency including all phases (milliseconds)
            fallback_used: Whether the fallback model was used instead of primary
        """
        invocation_log = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type=operation_type,
            athlete_id=athlete_id or 0,
            model_used=model_used,
            context_token_count=context_token_count,
            response_token_count=response_token_count,
            latency_ms=latency_ms,
            success_status=success,
            error_message=error_message,
            retrieval_latency_ms=retrieval_latency_ms,
            model_latency_ms=model_latency_ms,
            total_latency_ms=total_latency_ms,
            fallback_used=fallback_used,
        )

        self.invocation_logger.log(invocation_log)

    @staticmethod
    def _lc_msgs_to_dicts(messages: list) -> list:
        """Convert LangChain message objects to plain dicts for telemetry storage."""
        role_map = {"human": "user", "ai": "assistant", "system": "system"}
        result = []
        for m in messages:
            role = role_map.get(getattr(m, "type", ""), getattr(m, "type", "user"))
            content = getattr(m, "content", "")
            result.append({"role": role, "content": str(content)})
        return result

    def _persist_llm_call(
        self,
        source: str,
        model: str,
        messages: list,
        response_content: Optional[str],
        duration_ms: float,
        tool_calls: Optional[list] = None,
        error: Optional[str] = None,
    ) -> None:
        """Fire-and-forget persist to the llm_calls telemetry table."""
        try:
            from app.services.llm_trace_writer import write_llm_trace
            write_llm_trace(
                source=source,
                model=model or self.primary_model,
                messages=self._lc_msgs_to_dicts(messages),
                response_content=response_content,
                duration_ms=duration_ms,
                tool_calls=tool_calls,
                error=error,
            )
        except Exception:
            pass
