"""
LangChain Adapter Implementation

This module provides a LangChain-based implementation of the LLMProviderAdapter
interface, supporting Mixtral and Llama models via ChatOllama/ChatOpenAI with structured output.
"""

import time
import logging
from typing import Type, Optional
from datetime import datetime
import tiktoken
from pydantic import BaseModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
import requests.exceptions

from app.ai.adapter.llm_adapter import LLMProviderAdapter, LLMResponse
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
        
        # Track success and error for telemetry
        success = False
        error_message = None
        model_used = None
        parsed_output = None
        response_token_count = 0
        
        try:
            # Try primary model first
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
            
            # Calculate latency (includes retry time if fallback was used)
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Count response tokens
            response_token_count = self._count_response_tokens(parsed_output)
            
            # Mark as successful
            success = True
            
            # Log successful invocation
            self._log_invocation(
                operation_type=operation_type,
                athlete_id=athlete_id,
                model_used=model_used,
                context_token_count=context.token_count,
                response_token_count=response_token_count,
                latency_ms=latency_ms,
                success=True,
                error_message=None
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
                error_message=f"{type(e).__name__}: {str(e)}"
            )
            
            # Re-raise the exception
            raise
    
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
        error_message: Optional[str]
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
        """
        invocation_log = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type=operation_type,
            athlete_id=athlete_id or 0,  # Use 0 for unknown athlete_id
            model_used=model_used,
            context_token_count=context_token_count,
            response_token_count=response_token_count,
            latency_ms=latency_ms,
            success_status=success,
            error_message=error_message
        )
        
        self.invocation_logger.log(invocation_log)
