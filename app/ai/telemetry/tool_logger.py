"""
Tool invocation logging for LangChain tools.

This module provides the ToolLogger class for tracking all tool invocations
with telemetry including tool name, parameters, and result count.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ToolInvocationLog:
    """
    Telemetry record for a single tool invocation.
    
    Attributes:
        timestamp: ISO 8601 timestamp of the invocation
        tool_name: Name of the tool that was invoked
        parameters: Dictionary of parameters passed to the tool
        result_count: Number of results returned by the tool (0 if None returned)
        success_status: Whether the invocation succeeded (True) or failed (False)
        error_message: Error details if success_status is False, None otherwise
    """
    timestamp: str
    tool_name: str
    parameters: Dict[str, Any]
    result_count: int
    success_status: bool
    error_message: Optional[str] = None


class ToolLogger:
    """
    Logger for tool invocation telemetry.
    
    Writes tool invocation records to a JSONL file (one JSON object per line)
    for easy parsing and analysis. This provides an audit trail of all tool
    invocations for debugging and monitoring.
    """
    
    def __init__(
        self,
        log_file_path: str = "app/ai/telemetry/tool_invocations.jsonl"
    ):
        """
        Initialize the tool logger.
        
        Args:
            log_file_path: Path to the JSONL log file (default: app/ai/telemetry/tool_invocations.jsonl)
        """
        self.log_file_path = Path(log_file_path)
        # Ensure the directory exists
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, invocation: ToolInvocationLog) -> None:
        """
        Write a tool invocation log record to the JSONL file.
        
        Each invocation is written as a single line containing a JSON object.
        This format enables easy parsing and streaming analysis of logs.
        
        Args:
            invocation: The tool invocation log record to write
        """
        # Convert dataclass to dictionary
        log_dict = asdict(invocation)
        
        # Write as a single line of JSON
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            json.dump(log_dict, f, ensure_ascii=False)
            f.write('\n')
    
    def log_invocation(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Any,
        error: Optional[Exception] = None
    ) -> None:
        """
        Convenience method to log a tool invocation with automatic result counting.
        
        Args:
            tool_name: Name of the tool that was invoked
            parameters: Dictionary of parameters passed to the tool
            result: The result returned by the tool (can be list, dict, or None)
            error: Optional exception if the invocation failed
        """
        # Calculate result count
        result_count = 0
        if result is not None:
            if isinstance(result, list):
                result_count = len(result)
            elif isinstance(result, dict):
                result_count = 1
            else:
                result_count = 1
        
        # Create log entry
        log_entry = ToolInvocationLog(
            timestamp=datetime.now().isoformat(),
            tool_name=tool_name,
            parameters=parameters,
            result_count=result_count,
            success_status=error is None,
            error_message=str(error) if error else None
        )
        
        # Write to log
        self.log(log_entry)


# Global tool logger instance
_tool_logger = ToolLogger()


def get_tool_logger() -> ToolLogger:
    """
    Get the global tool logger instance.
    
    Returns:
        The global ToolLogger instance
    """
    return _tool_logger
