"""Unit tests for FileMover class."""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from .file_mover import FileMover
from .models import MoveResult, RemovalResult


class TestFileMover:
    """Test suite for FileMover class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def file_mover(self):
        """Create a FileMover instance."""
        return FileMover()
    
    def test_move_file_success(self, file_mover, temp_dir):
        """Test successful file move operation."""
        # Create source file
        source = temp_dir / "source.txt"
        source.write_text("test content")
        
        # Define destination
        destination = temp_dir / "dest" / "source.txt"
        
        # Move file
        result = file_mover.move_file(source, destination)
        
        # Verify result
        assert result.success is True
        assert result.source == source
        assert result.destination == destination
        assert result.error is None
        
        # Verify file exists at destination
        assert destination.exists()
        assert destination.read_text() == "test content"
        
        # Verify file no longer exists at source
        assert not source.exists()
    
    def test_move_file_source_not_exists(self, file_mover, temp_dir):
        """Test move operation when source file doesn't exist."""
        source = temp_dir / "nonexistent.txt"
        destination = temp_dir / "dest.txt"
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is False
        assert "Source file does not exist" in result.error
    
    def test_move_file_destination_exists(self, file_mover, temp_dir):
        """Test move operation when destination file already exists."""
        # Create source and destination files
        source = temp_dir / "source.txt"
        source.write_text("source content")
        
        destination = temp_dir / "dest.txt"
        destination.write_text("dest content")
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is False
        assert "Destination file already exists" in result.error
        
        # Verify source file still exists (move didn't happen)
        assert source.exists()
    
    def test_move_file_creates_destination_directory(self, file_mover, temp_dir):
        """Test that move operation creates destination directory if needed."""
        source = temp_dir / "source.txt"
        source.write_text("test content")
        
        # Destination in non-existent nested directory
        destination = temp_dir / "level1" / "level2" / "level3" / "source.txt"
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is True
        assert destination.exists()
        assert destination.read_text() == "test content"
    
    def test_move_file_preserves_permissions(self, file_mover, temp_dir):
        """Test that file permissions are preserved during move."""
        source = temp_dir / "source.txt"
        source.write_text("test content")
        
        # Get original permissions
        original_permissions = source.stat().st_mode
        
        destination = temp_dir / "dest" / "source.txt"
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is True
        
        # Verify permissions are preserved
        dest_permissions = destination.stat().st_mode
        assert dest_permissions == original_permissions
    
    def test_move_file_with_different_filename(self, file_mover, temp_dir):
        """Test moving file to a different filename."""
        source = temp_dir / "original.txt"
        source.write_text("test content")
        
        destination = temp_dir / "renamed.txt"
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is True
        assert destination.exists()
        assert destination.name == "renamed.txt"
        assert not source.exists()
    
    def test_move_file_preserves_content(self, file_mover, temp_dir):
        """Test that file content is preserved during move."""
        source = temp_dir / "source.txt"
        test_content = "This is test content with special chars: \n\t\r\x00"
        source.write_bytes(test_content.encode('utf-8'))
        
        destination = temp_dir / "dest" / "source.txt"
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is True
        assert destination.read_bytes() == test_content.encode('utf-8')
    
    def test_move_file_binary_content(self, file_mover, temp_dir):
        """Test moving file with binary content."""
        source = temp_dir / "binary.dat"
        binary_content = bytes(range(256))
        source.write_bytes(binary_content)
        
        destination = temp_dir / "dest" / "binary.dat"
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is True
        assert destination.read_bytes() == binary_content
    
    def test_move_file_empty_file(self, file_mover, temp_dir):
        """Test moving an empty file."""
        source = temp_dir / "empty.txt"
        source.touch()
        
        destination = temp_dir / "dest" / "empty.txt"
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is True
        assert destination.exists()
        assert destination.stat().st_size == 0
    
    def test_move_file_large_file(self, file_mover, temp_dir):
        """Test moving a large file."""
        source = temp_dir / "large.txt"
        # Create a 1MB file
        large_content = "x" * (1024 * 1024)
        source.write_text(large_content)
        
        destination = temp_dir / "dest" / "large.txt"
        
        result = file_mover.move_file(source, destination)
        
        assert result.success is True
        assert destination.exists()
        assert destination.stat().st_size == len(large_content)

    def test_remove_file_success(self, file_mover, temp_dir):
        """Test successful file removal."""
        # Create a file to remove
        file_path = temp_dir / "to_remove.txt"
        file_path.write_text("test content")
        
        # Remove file
        result = file_mover.remove_file(file_path, "Test removal")
        
        # Verify result
        assert result.success is True
        assert result.file_path == file_path
        assert result.reason == "Test removal"
        assert result.error is None
        
        # Verify file no longer exists
        assert not file_path.exists()
    
    def test_remove_file_not_exists(self, file_mover, temp_dir):
        """Test removal when file doesn't exist."""
        file_path = temp_dir / "nonexistent.txt"
        
        result = file_mover.remove_file(file_path, "Test removal")
        
        # With enhanced error handling, this is considered success (file is already gone)
        assert result.success is True
        assert "File does not exist" in result.error or "already removed" in result.error
    
    def test_remove_file_is_directory(self, file_mover, temp_dir):
        """Test removal when path is a directory, not a file."""
        dir_path = temp_dir / "test_dir"
        dir_path.mkdir()
        
        result = file_mover.remove_file(dir_path, "Test removal")
        
        assert result.success is False
        assert "Path is not a file" in result.error
        
        # Verify directory still exists
        assert dir_path.exists()
    
    def test_remove_file_removes_empty_directory(self, file_mover, temp_dir):
        """Test that empty directories are removed after file removal."""
        # Create nested directory with a file
        nested_dir = temp_dir / "level1" / "level2"
        nested_dir.mkdir(parents=True)
        file_path = nested_dir / "file.txt"
        file_path.write_text("test content")
        
        # Remove file
        result = file_mover.remove_file(file_path, "Test removal")
        
        assert result.success is True
        assert not file_path.exists()
        
        # Verify empty directory was removed
        assert not nested_dir.exists()
    
    def test_remove_file_preserves_non_empty_directory(self, file_mover, temp_dir):
        """Test that non-empty directories are preserved after file removal."""
        # Create directory with multiple files
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()
        file1 = test_dir / "file1.txt"
        file2 = test_dir / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")
        
        # Remove one file
        result = file_mover.remove_file(file1, "Test removal")
        
        assert result.success is True
        assert not file1.exists()
        
        # Verify directory still exists (not empty)
        assert test_dir.exists()
        assert file2.exists()
    
    def test_remove_file_does_not_remove_protected_directories(self, file_mover, temp_dir):
        """Test that protected directories are not removed even if empty."""
        # Create a protected directory name
        protected_dir = temp_dir / "app"
        protected_dir.mkdir()
        file_path = protected_dir / "file.txt"
        file_path.write_text("test content")
        
        # Remove file
        result = file_mover.remove_file(file_path, "Test removal")
        
        assert result.success is True
        assert not file_path.exists()
        
        # Verify protected directory still exists
        assert protected_dir.exists()
    
    def test_remove_file_with_special_characters(self, file_mover, temp_dir):
        """Test removing file with special characters in name."""
        file_path = temp_dir / "file with spaces & special-chars.txt"
        file_path.write_text("test content")
        
        result = file_mover.remove_file(file_path, "Test removal")
        
        assert result.success is True
        assert not file_path.exists()
    
    def test_remove_file_binary_file(self, file_mover, temp_dir):
        """Test removing a binary file."""
        file_path = temp_dir / "binary.dat"
        binary_content = bytes(range(256))
        file_path.write_bytes(binary_content)
        
        result = file_mover.remove_file(file_path, "Test removal")
        
        assert result.success is True
        assert not file_path.exists()
    
    def test_remove_file_empty_file(self, file_mover, temp_dir):
        """Test removing an empty file."""
        file_path = temp_dir / "empty.txt"
        file_path.touch()
        
        result = file_mover.remove_file(file_path, "Test removal")
        
        assert result.success is True
        assert not file_path.exists()
    
    def test_remove_file_large_file(self, file_mover, temp_dir):
        """Test removing a large file."""
        file_path = temp_dir / "large.txt"
        # Create a 1MB file
        large_content = "x" * (1024 * 1024)
        file_path.write_text(large_content)
        
        result = file_mover.remove_file(file_path, "Test removal")
        
        assert result.success is True
        assert not file_path.exists()

    def test_generate_cleanup_report_success(self, file_mover, temp_dir):
        """Test successful cleanup report generation."""
        from datetime import datetime
        from .models import CleanupReport, Operation, VerificationResults
        
        # Create a sample cleanup report
        report = CleanupReport(
            moved_to_wiki=[
                Operation(
                    type="move",
                    file_path=Path("MIGRATION_SUMMARY.md"),
                    destination=Path("wiki/MIGRATION_SUMMARY.md"),
                    reason="Documentation consolidation",
                    timestamp=datetime.now()
                )
            ],
            moved_to_tests=[
                Operation(
                    type="move",
                    file_path=Path("test_example.py"),
                    destination=Path("tests/test_example.py"),
                    reason="Test organization",
                    timestamp=datetime.now()
                )
            ],
            removed_files=[
                Operation(
                    type="remove",
                    file_path=Path("test_obsolete.py"),
                    reason="Obsolete test file",
                    timestamp=datetime.now()
                )
            ],
            preserved_files=[Path("important.py")],
            verification_results=VerificationResults(
                all_imports_valid=True,
                all_links_valid=True,
                pytest_discovery_success=True
            ),
            timestamp=datetime.now()
        )
        
        # Generate report
        output_path = temp_dir / "wiki" / "WORKSPACE_CLEANUP_REPORT.md"
        result_path = file_mover.generate_cleanup_report(report, output_path)
        
        # Verify report was created
        assert result_path == output_path
        assert output_path.exists()
        
        # Verify report content
        content = output_path.read_text()
        assert "# Workspace Cleanup Report" in content
        assert "## Files Moved to Wiki" in content
        assert "## Files Moved to Tests" in content
        assert "## Files Removed" in content
        assert "## Files Preserved" in content
        assert "## Verification Results" in content
        assert "MIGRATION_SUMMARY.md" in content
        assert "test_example.py" in content
        assert "test_obsolete.py" in content
        assert "important.py" in content
    
    def test_generate_cleanup_report_default_path(self, file_mover, temp_dir):
        """Test cleanup report generation with default path."""
        from datetime import datetime
        from .models import CleanupReport
        
        # Change to temp directory to test default path
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            
            # Create a minimal cleanup report
            report = CleanupReport(timestamp=datetime.now())
            
            # Generate report with default path
            result_path = file_mover.generate_cleanup_report(report)
            
            # Verify default path was used
            expected_path = Path("wiki") / "WORKSPACE_CLEANUP_REPORT.md"
            assert result_path == expected_path
            assert result_path.exists()
        finally:
            os.chdir(original_cwd)
    
    def test_generate_cleanup_report_creates_directory(self, file_mover, temp_dir):
        """Test that report generation creates output directory if needed."""
        from datetime import datetime
        from .models import CleanupReport
        
        # Create report with path in non-existent directory
        report = CleanupReport(timestamp=datetime.now())
        output_path = temp_dir / "level1" / "level2" / "report.md"
        
        result_path = file_mover.generate_cleanup_report(report, output_path)
        
        # Verify directory was created
        assert output_path.parent.exists()
        assert output_path.exists()
    
    def test_generate_cleanup_report_empty_report(self, file_mover, temp_dir):
        """Test generating report with no operations."""
        from datetime import datetime
        from .models import CleanupReport
        
        # Create empty report
        report = CleanupReport(timestamp=datetime.now())
        output_path = temp_dir / "report.md"
        
        result_path = file_mover.generate_cleanup_report(report, output_path)
        
        # Verify report was created
        assert output_path.exists()
        
        # Verify content shows empty sections
        content = output_path.read_text()
        assert "No files moved to wiki" in content
        assert "No files moved to tests" in content
        assert "No files removed" in content
    
    def test_generate_cleanup_report_with_verification_failures(self, file_mover, temp_dir):
        """Test report generation with verification failures."""
        from datetime import datetime
        from .models import CleanupReport, VerificationResults
        
        # Create report with verification failures
        report = CleanupReport(
            verification_results=VerificationResults(
                all_imports_valid=False,
                broken_imports=[(Path("test.py"), "from missing import module")],
                all_links_valid=False,
                broken_links=[(Path("doc.md"), "[broken](missing.md)")],
                pytest_discovery_success=False,
                pytest_errors=["Failed to collect tests"]
            ),
            timestamp=datetime.now()
        )
        
        output_path = temp_dir / "report.md"
        result_path = file_mover.generate_cleanup_report(report, output_path)
        
        # Verify report contains failure information
        content = output_path.read_text(encoding='utf-8')
        assert "Broken imports detected" in content
        assert "Broken links detected" in content
        assert "Pytest discovery issues" in content
        assert "from missing import module" in content
        assert "[broken](missing.md)" in content
        assert "Failed to collect tests" in content
    
    def test_generate_cleanup_report_with_justifications(self, file_mover, temp_dir):
        """Test that report includes justifications for removed files."""
        from datetime import datetime
        from .models import CleanupReport, Operation
        
        # Create report with removed files
        report = CleanupReport(
            removed_files=[
                Operation(
                    type="remove",
                    file_path=Path("test_old.py"),
                    reason="Superseded by test_new.py",
                    timestamp=datetime.now()
                ),
                Operation(
                    type="remove",
                    file_path=Path("test_debug.py"),
                    reason="Temporary debug file",
                    timestamp=datetime.now()
                )
            ],
            timestamp=datetime.now()
        )
        
        output_path = temp_dir / "report.md"
        result_path = file_mover.generate_cleanup_report(report, output_path)
        
        # Verify justifications are included
        content = output_path.read_text()
        assert "test_old.py" in content
        assert "Superseded by test_new.py" in content
        assert "test_debug.py" in content
        assert "Temporary debug file" in content
    
    def test_generate_cleanup_report_with_paths(self, file_mover, temp_dir):
        """Test that report includes original and destination paths."""
        from datetime import datetime
        from .models import CleanupReport, Operation
        
        # Create report with moved files
        report = CleanupReport(
            moved_to_wiki=[
                Operation(
                    type="move",
                    file_path=Path("README.md"),
                    destination=Path("wiki/README.md"),
                    timestamp=datetime.now()
                )
            ],
            moved_to_tests=[
                Operation(
                    type="move",
                    file_path=Path("test_api.py"),
                    destination=Path("tests/test_api.py"),
                    timestamp=datetime.now()
                )
            ],
            timestamp=datetime.now()
        )
        
        output_path = temp_dir / "report.md"
        result_path = file_mover.generate_cleanup_report(report, output_path)
        
        # Verify paths are included
        content = output_path.read_text(encoding='utf-8')
        assert "README.md" in content
        assert "wiki/README.md" in content
        assert "test_api.py" in content
        assert "tests/test_api.py" in content
        # Check for arrow character (may be encoded differently on different platforms)
        assert ("→" in content or "â†'" in content)  # Arrow showing source to destination
