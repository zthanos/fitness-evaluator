"""
Invocation telemetry logging for LLM calls.

This module provides the InvocationLogger class for tracking all LLM invocations
with detailed telemetry including token counts, latency, model used, and success status.
"""

import gzip
import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class InvocationLog:
    """
    Telemetry record for a single LLM invocation.
    
    Attributes:
        timestamp: ISO 8601 timestamp of the invocation
        operation_type: Type of operation (e.g., 'weekly_eval', 'chat_response')
        athlete_id: ID of the athlete for whom the operation was performed
        model_used: Name of the LLM model used (e.g., 'mixtral', 'llama')
        context_token_count: Number of tokens in the input context
        response_token_count: Number of tokens in the LLM response
        latency_ms: Time taken from context build to response parse (milliseconds)
        success_status: Whether the invocation succeeded (True) or failed (False)
        error_message: Error details if success_status is False, None otherwise
    """
    timestamp: str
    operation_type: str
    athlete_id: int
    model_used: str
    context_token_count: int
    response_token_count: int
    latency_ms: float
    success_status: bool
    error_message: Optional[str] = None


class InvocationLogger:
    """
    Logger for LLM invocation telemetry.
    
    Writes invocation records to a JSONL file (one JSON object per line)
    for easy parsing and analysis. Implements daily log rotation with
    30-day retention to prevent unbounded growth.
    """
    
    def __init__(
        self,
        log_file_path: str = "app/ai/telemetry/invocations.jsonl",
        retention_days: int = 30
    ):
        """
        Initialize the invocation logger.
        
        Args:
            log_file_path: Path to the JSONL log file (default: app/ai/telemetry/invocations.jsonl)
            retention_days: Number of days to retain archived logs (default: 30)
        """
        self.log_file_path = Path(log_file_path)
        self.retention_days = retention_days
        # Ensure the directory exists
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, invocation: InvocationLog) -> None:
        """
        Write an invocation log record to the JSONL file.
        
        Each invocation is written as a single line containing a JSON object.
        This format enables easy parsing and streaming analysis of logs.
        
        Automatically triggers log rotation if needed.
        
        Args:
            invocation: The invocation log record to write
        """
        # Check if rotation is needed before logging
        self._rotate_if_needed()
        
        # Always cleanup old archives when logging (even if no rotation occurred)
        self._cleanup_old_archives()
        
        # Convert dataclass to dictionary
        log_dict = asdict(invocation)
        
        # Write as a single line of JSON
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            json.dump(log_dict, f, ensure_ascii=False)
            f.write('\n')
    
    def _rotate_if_needed(self) -> None:
        """
        Check if log rotation is needed and perform rotation if necessary.
        
        Rotation is triggered if:
        1. The log file exists
        2. The log file's last modification date is not today
        
        When rotating:
        1. Archive current log to invocations_YYYY-MM-DD.jsonl.gz
        2. Create new empty log file (happens automatically on next write)
        """
        if not self.log_file_path.exists():
            return
        
        # Get the last modification time of the log file
        mtime = datetime.fromtimestamp(self.log_file_path.stat().st_mtime)
        today = datetime.now().date()
        
        # If the file was last modified today, no rotation needed
        if mtime.date() == today:
            return
        
        # Perform rotation
        self._rotate_log()
    
    def _rotate_log(self) -> None:
        """
        Rotate the current log file by archiving it with gzip compression.
        
        The archived file is named invocations_YYYY-MM-DD.jsonl.gz where
        the date represents the last modification date of the log file.
        """
        if not self.log_file_path.exists() or self.log_file_path.stat().st_size == 0:
            return
        
        # Get the last modification date for the archive filename
        mtime = datetime.fromtimestamp(self.log_file_path.stat().st_mtime)
        archive_date = mtime.strftime("%Y-%m-%d")
        archive_name = f"invocations_{archive_date}.jsonl.gz"
        archive_path = self.log_file_path.parent / archive_name
        
        # Compress and archive the current log file
        with open(self.log_file_path, 'rb') as f_in:
            with gzip.open(archive_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove the original log file after successful archiving
        self.log_file_path.unlink()
    
    def _cleanup_old_archives(self) -> None:
        """
        Delete archived log files older than the retention period.
        
        Scans the log directory for archived files matching the pattern
        invocations_YYYY-MM-DD.jsonl.gz and deletes those older than
        retention_days.
        """
        if not self.log_file_path.parent.exists():
            return
        
        cutoff_date = datetime.now().date() - timedelta(days=self.retention_days)
        
        # Find all archived log files
        for archive_file in self.log_file_path.parent.glob("invocations_*.jsonl.gz"):
            try:
                # Extract date from filename (invocations_YYYY-MM-DD.jsonl.gz)
                date_str = archive_file.stem.replace("invocations_", "").replace(".jsonl", "")
                archive_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # Delete if older than retention period
                if archive_date < cutoff_date:
                    archive_file.unlink()
            except (ValueError, IndexError):
                # Skip files that don't match the expected format
                continue
