"""
LLM Provider Adapter Interface

This module defines the abstract interface for LLM provider adapters,
enabling model-agnostic invocation with structured output contracts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Type
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
