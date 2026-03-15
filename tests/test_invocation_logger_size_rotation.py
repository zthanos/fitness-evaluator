"""
Tests for InvocationLogger size-based log rotation and data integrity.

Validates:
- 5.4.2: Log file size limits trigger rotation
- 5.4.4: Rotation doesn't lose data (all records recoverable from log + archives)
"""

import gzip
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from app.ai.telemetry.invocation_logger import InvocationLogger, InvocationLog


def _make_invocation(athlete_id: int = 123, op: str = "chat_response") -> InvocationLog:
    return InvocationLog(
        timestamp=datetime.now().isoformat(),
        operation_type=op,
        athlete_id=athlete_id,
        model_used="mixtral",
        context_token_count=2500,
        response_token_count=500,
        latency_ms=1234.5,
        success_status=True,
        error_message=None,
    )


def _count_all_records(tmpdir: str, log_path: Path) -> list[dict]:
    """Collect all records from the active log and all archives."""
    records = []
    # Active log
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    # Archives
    for archive in Path(tmpdir).glob("invocations_*.jsonl.gz"):
        with gzip.open(archive, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    return records


def test_size_based_rotation_triggers():
    """Test that rotation triggers when log file exceeds max_size_bytes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        # Use a tiny size limit so rotation triggers quickly
        logger = InvocationLogger(
            log_file_path=str(log_path),
            retention_days=30,
            max_size_bytes=500,
        )

        # Write entries until we exceed the size limit
        for i in range(20):
            logger.log(_make_invocation(athlete_id=i))

        # There should be at least one archive from size-based rotation
        archives = list(Path(tmpdir).glob("invocations_*.jsonl.gz"))
        assert len(archives) >= 1, "Size-based rotation should create at least one archive"

        # Active log should exist and be under the limit (or freshly written)
        assert log_path.exists()


def test_size_rotation_creates_suffixed_archives():
    """Test that multiple size rotations on the same day produce unique archive names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(
            log_file_path=str(log_path),
            retention_days=30,
            max_size_bytes=300,  # very small to force multiple rotations
        )

        for i in range(30):
            logger.log(_make_invocation(athlete_id=i))

        archives = sorted(Path(tmpdir).glob("invocations_*.jsonl.gz"))
        # With a 300-byte limit we should get multiple archives
        assert len(archives) >= 2, f"Expected multiple archives, got {len(archives)}"

        # Verify archive names are unique (no overwrites)
        names = [a.name for a in archives]
        assert len(names) == len(set(names)), "Archive names must be unique"


def test_size_rotation_no_data_loss():
    """Test that all logged records are recoverable after size-based rotations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        total_records = 50
        logger = InvocationLogger(
            log_file_path=str(log_path),
            retention_days=30,
            max_size_bytes=500,
        )

        for i in range(total_records):
            logger.log(_make_invocation(athlete_id=i))

        all_records = _count_all_records(tmpdir, log_path)
        assert len(all_records) == total_records, (
            f"Expected {total_records} records total, got {len(all_records)}"
        )

        # Verify each athlete_id is present exactly once
        ids = sorted(r["athlete_id"] for r in all_records)
        assert ids == list(range(total_records))


def test_date_rotation_no_data_loss():
    """Test that all logged records are recoverable after date-based rotation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path), retention_days=30)

        # Log entries for "yesterday"
        for i in range(5):
            logger.log(_make_invocation(athlete_id=i))

        # Simulate the file being from yesterday
        yesterday = datetime.now() - timedelta(days=1)
        os.utime(log_path, (yesterday.timestamp(), yesterday.timestamp()))

        # Log entries for "today" — triggers date rotation
        for i in range(5, 10):
            logger.log(_make_invocation(athlete_id=i))

        all_records = _count_all_records(tmpdir, log_path)
        assert len(all_records) == 10, f"Expected 10 records, got {len(all_records)}"

        ids = sorted(r["athlete_id"] for r in all_records)
        assert ids == list(range(10))


def test_mixed_date_and_size_rotation_no_data_loss():
    """Test no data loss when both date and size rotations occur."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(
            log_file_path=str(log_path),
            retention_days=30,
            max_size_bytes=500,
        )

        # Phase 1: log some entries (may trigger size rotation)
        for i in range(15):
            logger.log(_make_invocation(athlete_id=i))

        # Simulate the file being from yesterday
        if log_path.exists():
            yesterday = datetime.now() - timedelta(days=1)
            os.utime(log_path, (yesterday.timestamp(), yesterday.timestamp()))

        # Phase 2: log more entries (triggers date rotation, then possibly size)
        for i in range(15, 30):
            logger.log(_make_invocation(athlete_id=i))

        all_records = _count_all_records(tmpdir, log_path)
        assert len(all_records) == 30, f"Expected 30 records, got {len(all_records)}"

        ids = sorted(r["athlete_id"] for r in all_records)
        assert ids == list(range(30))


def test_default_max_size_is_10mb():
    """Test that the default max_size_bytes is 10 MB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path))
        assert logger.max_size_bytes == 10 * 1024 * 1024


def test_cleanup_handles_suffixed_archives():
    """Test that retention cleanup also removes suffixed archive files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "invocations.jsonl"
        logger = InvocationLogger(
            log_file_path=str(log_path),
            retention_days=7,
        )

        today = datetime.now().date()
        old_date = today - timedelta(days=10)
        date_str = old_date.strftime("%Y-%m-%d")

        # Create suffixed archives that are past retention
        for suffix in ["", "_1", "_2"]:
            archive = Path(tmpdir) / f"invocations_{date_str}{suffix}.jsonl.gz"
            with gzip.open(archive, "wt", encoding="utf-8") as f:
                f.write('{"test": "old"}\n')

        # Trigger cleanup via a log call
        logger.log(_make_invocation())

        remaining = list(Path(tmpdir).glob(f"invocations_{date_str}*.jsonl.gz"))
        assert len(remaining) == 0, "All old suffixed archives should be cleaned up"
