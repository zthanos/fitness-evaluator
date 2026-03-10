"""
Tool Execution Framework

Provides a centralized framework for executing LLM tools with user_id scoping,
validation, error handling, and logging.
"""

from typing import Dict, Any, Callable, Optional
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass


class ToolExecutor:
    """
    Centralized tool execution framework with user_id scoping.
    
    All tools MUST:
    1. Validate user_id is present
    2. Filter all database queries by user_id
    3. Log tool invocation
    4. Handle errors gracefully
    """
    
    def __init__(self, db: Session, user_id: int):
        """
        Initialize tool executor.
        
        Args:
            db: SQLAlchemy database session
            user_id: User ID for scoping all data access
        """
        self.db = db
        self.user_id = user_id
        self._validate_user_id()
    
    def _validate_user_id(self) -> None:
        """
        Validate that user_id is present and valid.
        
        Raises:
            ToolExecutionError: If user_id is invalid
        """
        if not self.user_id:
            raise ToolExecutionError("user_id is required for tool execution")
        
        if not isinstance(self.user_id, int) or self.user_id <= 0:
            raise ToolExecutionError(f"Invalid user_id: {self.user_id}")
    
    def execute(
        self,
        tool_name: str,
        tool_func: Callable,
        parameters: Dict[str, Any],
        inject_user_id: bool = True
    ) -> Any:
        """
        Execute a tool with validation, logging, and error handling.
        
        Args:
            tool_name: Name of the tool being executed
            tool_func: Tool function to execute
            parameters: Tool parameters
            inject_user_id: Whether to inject user_id into parameters
        
        Returns:
            Tool execution result
        
        Raises:
            ToolExecutionError: If execution fails
        """
        try:
            # Log invocation
            logger.info(
                f"Executing tool: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "user_id": self.user_id,
                    "parameters": parameters
                }
            )
            
            # Inject user_id if requested
            if inject_user_id:
                parameters = {**parameters, "user_id": self.user_id}
            
            # Execute tool
            result = tool_func(**parameters)
            
            # Log success
            logger.info(
                f"Tool execution successful: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "user_id": self.user_id,
                    "success": True
                }
            )
            
            return result
            
        except Exception as e:
            # Log error
            logger.error(
                f"Tool execution failed: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "user_id": self.user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            
            raise ToolExecutionError(f"Tool execution failed: {str(e)}") from e
    
    async def execute_async(
        self,
        tool_name: str,
        tool_func: Callable,
        parameters: Dict[str, Any],
        inject_user_id: bool = True
    ) -> Any:
        """
        Execute an async tool with validation, logging, and error handling.
        
        Args:
            tool_name: Name of the tool being executed
            tool_func: Async tool function to execute
            parameters: Tool parameters
            inject_user_id: Whether to inject user_id into parameters
        
        Returns:
            Tool execution result
        
        Raises:
            ToolExecutionError: If execution fails
        """
        try:
            # Log invocation
            logger.info(
                f"Executing async tool: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "user_id": self.user_id,
                    "parameters": parameters
                }
            )
            
            # Inject user_id if requested
            if inject_user_id:
                parameters = {**parameters, "user_id": self.user_id}
            
            # Execute tool
            result = await tool_func(**parameters)
            
            # Log success
            logger.info(
                f"Async tool execution successful: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "user_id": self.user_id,
                    "success": True
                }
            )
            
            return result
            
        except Exception as e:
            # Log error
            logger.error(
                f"Async tool execution failed: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "user_id": self.user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            
            raise ToolExecutionError(f"Async tool execution failed: {str(e)}") from e


def create_tool_executor(db: Session, user_id: int) -> ToolExecutor:
    """
    Factory function to create a tool executor.
    
    Args:
        db: SQLAlchemy database session
        user_id: User ID for scoping
    
    Returns:
        ToolExecutor instance
    """
    return ToolExecutor(db, user_id)
