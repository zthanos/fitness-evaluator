"""
Unit tests for InvocationLogger log rotation functionality.

Tests the daily log rotation with 30-day retention:
- Rotation triggers when log file is from a previous day
- Old logs are archived to invocations_YYYY-MM-DD.jsonl.gz
- Archives older than 30 days are deleted
"""

import gzip
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from app.ai.telemetry.invocation_logger import InvocationLogger, InvocationLog


def test_log_rotation_triggers_on_old_file():
    """Test that rotation is triggered when log file is from a previous day."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path), retention_days=30)
        
        # Create a log entry
        invocation = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        logger.log(invocation)
        
        # Verify log file exists
        assert log_path.exists(), "Log file should exist"
        
        # Modify the file's timestamp to simulate it being from yesterday
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_timestamp = yesterday.timestamp()
        os.utime(log_path, (yesterday_timestamp, yesterday_timestamp))
        
        # Log another entry (should trigger rotation)
        invocation2 = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="chat_response",
            athlete_id=456,
            model_used="llama",
            context_token_count=1800,
            response_token_count=300,
            latency_ms=987.3,
            success_status=True,
            error_message=None
        )
        logger.log(invocation2)
        
        # Check that archive was created
        archive_date = yesterday.strftime("%Y-%m-%d")
        archive_path = Path(tmpdir) / f"invocations_{archive_date}.jsonl.gz"
        assert archive_path.exists(), f"Archive file should exist: {archive_path}"
        
        # Verify the new log file contains only the second entry
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 1, "New log file should contain only the second entry"
        
        # Verify the archive contains the first entry
        with gzip.open(archive_path, 'rt', encoding='utf-8') as f:
            archived_lines = f.readlines()
        assert len(archived_lines) == 1, "Archive should contain the first entry"
        archived_log = json.loads(archived_lines[0])
        assert archived_log['athlete_id'] == 123


def test_log_rotation_no_rotation_same_day():
    """Test that rotation does not occur when logging on the same day."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path), retention_days=30)
        
        # Create two log entries on the same day
        invocation1 = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        logger.log(invocation1)
        
        invocation2 = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="chat_response",
            athlete_id=456,
            model_used="llama",
            context_token_count=1800,
            response_token_count=300,
            latency_ms=987.3,
            success_status=True,
            error_message=None
        )
        logger.log(invocation2)
        
        # Verify both entries are in the same log file
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 2, "Both entries should be in the same log file"
        
        # Verify no archive files were created
        archive_files = list(Path(tmpdir).glob("invocations_*.jsonl.gz"))
        assert len(archive_files) == 0, "No archive files should be created"


def test_log_rotation_archive_format():
    """Test that archived logs are compressed with gzip and named correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path), retention_days=30)
        
        # Create a log entry
        invocation = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        logger.log(invocation)
        
        # Set file timestamp to 2 days ago
        two_days_ago = datetime.now() - timedelta(days=2)
        two_days_ago_timestamp = two_days_ago.timestamp()
        os.utime(log_path, (two_days_ago_timestamp, two_days_ago_timestamp))
        
        # Trigger rotation
        logger.log(invocation)
        
        # Verify archive file name format
        archive_date = two_days_ago.strftime("%Y-%m-%d")
        archive_path = Path(tmpdir) / f"invocations_{archive_date}.jsonl.gz"
        assert archive_path.exists(), "Archive should exist with correct name format"
        
        # Verify the archive is gzip compressed and contains valid JSON
        with gzip.open(archive_path, 'rt', encoding='utf-8') as f:
            content = f.read()
            lines = content.strip().split('\n')
            assert len(lines) == 1, "Archive should contain one log entry"
            log_data = json.loads(lines[0])
            assert log_data['athlete_id'] == 123


def test_log_rotation_cleanup_old_archives():
    """Test that archives older than retention period are deleted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        retention_days = 30
        logger = InvocationLogger(log_file_path=str(log_path), retention_days=retention_days)
        
        # Create mock archive files with different dates
        today = datetime.now().date()
        
        # Create an archive from 25 days ago (should be kept)
        recent_date = today - timedelta(days=25)
        recent_archive = Path(tmpdir) / f"invocations_{recent_date.strftime('%Y-%m-%d')}.jsonl.gz"
        with gzip.open(recent_archive, 'wt', encoding='utf-8') as f:
            f.write('{"test": "recent"}\n')
        
        # Create an archive from 35 days ago (should be deleted)
        old_date = today - timedelta(days=35)
        old_archive = Path(tmpdir) / f"invocations_{old_date.strftime('%Y-%m-%d')}.jsonl.gz"
        with gzip.open(old_archive, 'wt', encoding='utf-8') as f:
            f.write('{"test": "old"}\n')
        
        # Create an archive from 31 days ago (should be deleted)
        very_old_date = today - timedelta(days=31)
        very_old_archive = Path(tmpdir) / f"invocations_{very_old_date.strftime('%Y-%m-%d')}.jsonl.gz"
        with gzip.open(very_old_archive, 'wt', encoding='utf-8') as f:
            f.write('{"test": "very_old"}\n')
        
        # Verify all archives exist before cleanup
        assert recent_archive.exists()
        assert old_archive.exists()
        assert very_old_archive.exists()
        
        # Trigger rotation (which includes cleanup)
        invocation = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        logger.log(invocation)
        
        # Verify recent archive still exists
        assert recent_archive.exists(), "Recent archive (25 days old) should be kept"
        
        # Verify old archives were deleted
        assert not old_archive.exists(), "Old archive (35 days old) should be deleted"
        assert not very_old_archive.exists(), "Very old archive (31 days old) should be deleted"


def test_log_rotation_empty_file_not_archived():
    """Test that empty log files are not archived."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path), retention_days=30)
        
        # Create an empty log file
        log_path.touch()
        
        # Set file timestamp to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_timestamp = yesterday.timestamp()
        os.utime(log_path, (yesterday_timestamp, yesterday_timestamp))
        
        # Trigger rotation
        invocation = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        logger.log(invocation)
        
        # Verify no archive was created for the empty file
        archive_files = list(Path(tmpdir).glob("invocations_*.jsonl.gz"))
        assert len(archive_files) == 0, "Empty log files should not be archived"


def test_log_rotation_multiple_rotations():
    """Test that multiple rotations work correctly over time."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path), retention_days=30)
        
        # Simulate logging over 3 days
        for day_offset in range(3):
            # Create a log entry
            invocation = InvocationLog(
                timestamp=datetime.now().isoformat(),
                operation_type="weekly_eval",
                athlete_id=100 + day_offset,
                model_used="mixtral",
                context_token_count=2500,
                response_token_count=500,
                latency_ms=1234.5,
                success_status=True,
                error_message=None
            )
            logger.log(invocation)
            
            # If not the last day, modify timestamp to simulate next day
            if day_offset < 2:
                target_date = datetime.now() - timedelta(days=2 - day_offset)
                target_timestamp = target_date.timestamp()
                os.utime(log_path, (target_timestamp, target_timestamp))
        
        # Verify we have 2 archive files (days 0 and 1)
        archive_files = list(Path(tmpdir).glob("invocations_*.jsonl.gz"))
        assert len(archive_files) == 2, "Should have 2 archived files"
        
        # Verify current log file has only the last entry
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 1, "Current log should have only the last entry"
        log_data = json.loads(lines[0])
        assert log_data['athlete_id'] == 102


def test_log_rotation_custom_retention_period():
    """Test that custom retention periods work correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        retention_days = 7  # Custom 7-day retention
        logger = InvocationLogger(log_file_path=str(log_path), retention_days=retention_days)
        
        today = datetime.now().date()
        
        # Create an archive from 5 days ago (should be kept)
        recent_date = today - timedelta(days=5)
        recent_archive = Path(tmpdir) / f"invocations_{recent_date.strftime('%Y-%m-%d')}.jsonl.gz"
        with gzip.open(recent_archive, 'wt', encoding='utf-8') as f:
            f.write('{"test": "recent"}\n')
        
        # Create an archive from 10 days ago (should be deleted with 7-day retention)
        old_date = today - timedelta(days=10)
        old_archive = Path(tmpdir) / f"invocations_{old_date.strftime('%Y-%m-%d')}.jsonl.gz"
        with gzip.open(old_archive, 'wt', encoding='utf-8') as f:
            f.write('{"test": "old"}\n')
        
        # Trigger rotation
        invocation = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        logger.log(invocation)
        
        # Verify recent archive still exists
        assert recent_archive.exists(), "Recent archive (5 days old) should be kept"
        
        # Verify old archive was deleted
        assert not old_archive.exists(), "Old archive (10 days old) should be deleted with 7-day retention"


if __name__ == "__main__":
    test_log_rotation_triggers_on_old_file()
    test_log_rotation_no_rotation_same_day()
    test_log_rotation_archive_format()
    test_log_rotation_cleanup_old_archives()
    test_log_rotation_empty_file_not_archived()
    test_log_rotation_multiple_rotations()
    test_log_rotation_custom_retention_period()
    print("All log rotation tests passed!")
