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
        retrieval_latency_ms: Time spent on RAG/context retrieval (milliseconds)
        model_latency_ms: Time spent on LLM model invocation (milliseconds)
        total_latency_ms: End-to-end latency including all phases (milliseconds)
        fallback_used: Whether the fallback model was used instead of primary
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
    retrieval_latency_ms: Optional[float] = None
    model_latency_ms: Optional[float] = None
    total_latency_ms: Optional[float] = None
    fallback_used: Optional[bool] = None




class InvocationLogger:
    """
    Logger for LLM invocation telemetry.
    
    Writes invocation records to a JSONL file (one JSON object per line)
    for easy parsing and analysis. Implements daily log rotation with
    30-day retention to prevent unbounded growth.
    """
    
    DEFAULT_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

    def __init__(
        self,
        log_file_path: str = "app/ai/telemetry/invocations.jsonl",
        retention_days: int = 30,
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES
    ):
        """
        Initialize the invocation logger.
        
        Args:
            log_file_path: Path to the JSONL log file (default: app/ai/telemetry/invocations.jsonl)
            retention_days: Number of days to retain archived logs (default: 30)
            max_size_bytes: Maximum log file size in bytes before rotation (default: 10 MB)
        """
        self.log_file_path = Path(log_file_path)
        self.retention_days = retention_days
        self.max_size_bytes = max_size_bytes
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
        1. The log file exists AND
        2. The log file's last modification date is not today, OR
        3. The log file exceeds max_size_bytes
        
        When rotating:
        1. Archive current log to invocations_YYYY-MM-DD.jsonl.gz
        2. Create new empty log file (happens automatically on next write)
        """
        if not self.log_file_path.exists():
            return
        
        stat = self.log_file_path.stat()
        
        # Check size-based rotation first
        if stat.st_size >= self.max_size_bytes:
            self._rotate_log()
            return
        
        # Check date-based rotation
        mtime = datetime.fromtimestamp(stat.st_mtime)
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
        If an archive for that date already exists (e.g. from size-based
        rotation), a numeric suffix is appended: invocations_YYYY-MM-DD_1.jsonl.gz
        """
        if not self.log_file_path.exists() or self.log_file_path.stat().st_size == 0:
            return
        
        # Get the last modification date for the archive filename
        mtime = datetime.fromtimestamp(self.log_file_path.stat().st_mtime)
        archive_date = mtime.strftime("%Y-%m-%d")
        archive_name = f"invocations_{archive_date}.jsonl.gz"
        archive_path = self.log_file_path.parent / archive_name
        
        # If archive already exists (size-based rotation on same day), add suffix
        if archive_path.exists():
            suffix = 1
            while True:
                archive_name = f"invocations_{archive_date}_{suffix}.jsonl.gz"
                archive_path = self.log_file_path.parent / archive_name
                if not archive_path.exists():
                    break
                suffix += 1
        
        # Compress and archive the current log file
        with open(self.log_file_path, 'rb') as f_in:
            with gzip.open(archive_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove the original log file after successful archiving
        self.log_file_path.unlink()
    
    def _cleanup_old_archives(self) -> None:
        """
        Delete archived log files older than the retention period.
        
        Scans the log directory for archived files matching the patterns
        invocations_YYYY-MM-DD.jsonl.gz and invocations_YYYY-MM-DD_N.jsonl.gz
        and deletes those older than retention_days.
        """
        if not self.log_file_path.parent.exists():
            return
        
        cutoff_date = datetime.now().date() - timedelta(days=self.retention_days)
        
        # Find all archived log files
        for archive_file in self.log_file_path.parent.glob("invocations_*.jsonl.gz"):
            try:
                # Extract date from filename
                # Handles both invocations_YYYY-MM-DD.jsonl.gz
                # and invocations_YYYY-MM-DD_N.jsonl.gz
                stem = archive_file.stem.replace(".jsonl", "")  # remove .jsonl from .jsonl.gz
                name_part = stem.replace("invocations_", "")
                # Take only the date portion (first 10 chars: YYYY-MM-DD)
                date_str = name_part[:10]
                archive_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # Delete if older than retention period
                if archive_date < cutoff_date:
                    archive_file.unlink()
            except (ValueError, IndexError):
                # Skip files that don't match the expected format
                continue
