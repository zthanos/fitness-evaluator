"""
Context Builder Base Class

This module provides the foundation for building structured, layered contexts
for LLM invocations with token budget enforcement and validation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
import tiktoken


@dataclass
class Context:
    """Structured context object with typed layers"""
    system_instructions: str
    task_instructions: str
    domain_knowledge: Dict[str, Any]
    retrieved_data: List[Dict[str, Any]]
    conversation_history: Optional[List[Dict[str, str]]] = None
    token_count: int = 0
    
    def to_messages(self) -> List[Dict[str, str]]:
        """Convert to LangChain message format"""
        messages = [
            {"role": "system", "content": self.system_instructions},
            {"role": "user", "content": self._format_task_and_data()}
        ]
        if self.conversation_history:
            messages.extend(self.conversation_history)
        return messages
    
    def _format_task_and_data(self) -> str:
        """Format task instructions, domain knowledge, and retrieved data"""
        parts = [
            "# Task Instructions",
            self.task_instructions,
            "",
            "# Domain Knowledge",
            json.dumps(self.domain_knowledge, indent=2),
            "",
            "# Retrieved Data",
            json.dumps(self.retrieved_data, indent=2)
        ]
        return "\n".join(parts)


class ContextBudgetExceeded(Exception):
    """Raised when context exceeds token budget"""
    def __init__(self, actual: int, budget: int):
        self.actual = actual
        self.budget = budget
        super().__init__(f"Context size {actual} exceeds budget {budget}")


class ContextBuilder(ABC):
    """Base class for context builders with fluent interface"""
    
    def __init__(self, token_budget: int):
        self.token_budget = token_budget
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self._system_instructions: Optional[str] = None
        self._task_instructions: Optional[str] = None
        self._domain_knowledge: Optional[Dict] = None
        self._retrieved_data: List[Dict] = []
        self._conversation_history: List[Dict] = []
    
    def add_system_instructions(self, instructions: str) -> 'ContextBuilder':
        """Add system instructions layer"""
        self._system_instructions = instructions
        return self
    
    def add_task_instructions(self, instructions: str) -> 'ContextBuilder':
        """Add task instructions layer"""
        self._task_instructions = instructions
        return self
    
    def add_domain_knowledge(self, knowledge: Dict[str, Any]) -> 'ContextBuilder':
        """Add domain knowledge layer"""
        self._domain_knowledge = knowledge
        return self
    
    def add_retrieved_data(self, data: List[Dict[str, Any]]) -> 'ContextBuilder':
        """Add retrieved data layer"""
        self._retrieved_data.extend(data)
        return self
    
    def add_conversation_history(self, history: List[Dict[str, str]]) -> 'ContextBuilder':
        """Add conversation history (for chat operations)"""
        self._conversation_history = history
        return self
    
    def build(self) -> Context:
        """Build and validate context"""
        # Validate required layers
        if not self._system_instructions:
            raise ValueError("System instructions required")
        if not self._task_instructions:
            raise ValueError("Task instructions required")
        
        # Create context object
        context = Context(
            system_instructions=self._system_instructions,
            task_instructions=self._task_instructions,
            domain_knowledge=self._domain_knowledge or {},
            retrieved_data=self._retrieved_data,
            conversation_history=self._conversation_history if self._conversation_history else None
        )
        
        # Count tokens
        context.token_count = self._count_tokens(context)
        
        # Validate budget
        if context.token_count > self.token_budget:
            raise ContextBudgetExceeded(context.token_count, self.token_budget)
        
        return context
    
    def _count_tokens(self, context: Context) -> int:
        """Count tokens in context using tiktoken"""
        messages = context.to_messages()
        total = 0
        for message in messages:
            # Count tokens in message content
            total += len(self.encoding.encode(message["content"]))
            # Add overhead for message formatting (role, etc.)
            total += 4
        return total
    
    @abstractmethod
    def gather_data(self, **kwargs) -> 'ContextBuilder':
        """Gather operation-specific data (implemented by subclasses)"""
        pass
