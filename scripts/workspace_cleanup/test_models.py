"""Tests for workspace cleanup data models."""

import pytest
from pathlib import Path
from datetime import datetime
from hypothesis import given, strategies as st

from scripts.workspace_cleanup.models import (
    FileInventory,
    CleanupPlan,
    CleanupReport,
    ObsolescenceReport,
    ContentEvaluation,
    SafetyReport,
    MoveResult,
    RemovalResult,
    Operation,
    VerificationResults,
)


class TestFileInventory:
    """Tests for FileInventory data model."""
    
    def test_empty_inventory(self):
        """Test empty inventory has zero files to process."""
        inventory = FileInventory()
        assert inventory.total_files_to_process() == 0
    
    def test_inventory_with_files(self):
        """Test inventory correctly counts files."""
        inventory = FileInventory(
            root_documentation=[Path("doc1.md"), Path("doc2.md")],
            root_tests_py=[Path("test1.py"), Path("test2.py"), Path("test3.py")],
            root_tests_html=[Path("test.html")],
            root_tests_db=[Path("test.db")],
            specs_files=[Path("spec.md")],
        )
        assert inventory.total_files_to_process() == 8


class TestCleanupPlan:
    """Tests for CleanupPlan data model."""
    
    def test_empty_plan_is_valid(self):
        """Test empty cleanup plan has no validation errors."""
        plan = CleanupPlan()
        errors = plan.validate()
        assert errors == []
    
    def test_plan_with_unique_files_is_valid(self):
        """Test plan with unique files in each operation is valid."""
        plan = CleanupPlan(
            files_to_move_to_wiki=[(Path("doc.md"), Path("wiki/doc.md"))],
            files_to_move_to_tests=[(Path("test.py"), Path("tests/test.py"))],
            files_to_remove=[(Path("old.py"), "obsolete")],
            files_to_preserve=[Path("keep.py")],
        )
        errors = plan.validate()
        assert errors == []
    
    def test_plan_with_duplicate_file_is_invalid(self):
        """Test plan with same file in multiple operations is invalid."""
        duplicate_file = Path("test.py")
        plan = CleanupPlan(
            files_to_move_to_wiki=[(duplicate_file, Path("wiki/test.py"))],
            files_to_move_to_tests=[(duplicate_file, Path("tests/test.py"))],
        )
        errors = plan.validate()
        assert len(errors) > 0
        assert any("appears in multiple operations" in error for error in errors)


class TestObsolescenceReport:
    """Tests for ObsolescenceReport data model."""
    
    def test_obsolete_report_creation(self):
        """Test creating an obsolescence report."""
        report = ObsolescenceReport(
            file_path=Path("test_old.py"),
            is_obsolete=True,
            reason="Duplicate functionality",
            confidence=0.9,
        )
        assert report.is_obsolete
        assert report.confidence == 0.9
        assert "Duplicate" in report.reason


class TestContentEvaluation:
    """Tests for ContentEvaluation data model."""
    
    def test_valuable_content_evaluation(self):
        """Test creating a content evaluation for valuable content."""
        evaluation = ContentEvaluation(
            file_path=Path("specs/plan.md"),
            has_value=True,
            reason="Contains unique technical details",
            recommended_action="move_to_wiki",
        )
        assert evaluation.has_value
        assert evaluation.recommended_action == "move_to_wiki"


class TestSafetyReport:
    """Tests for SafetyReport data model."""
    
    def test_safe_to_remove(self):
        """Test creating a safety report for safe removal."""
        report = SafetyReport(
            file_path=Path("test_old.py"),
            is_safe_to_remove=True,
        )
        assert report.is_safe_to_remove
        assert len(report.blocking_imports) == 0
    
    def test_not_safe_to_remove(self):
        """Test creating a safety report with blocking dependencies."""
        report = SafetyReport(
            file_path=Path("helper.py"),
            is_safe_to_remove=False,
            blocking_imports=["app.main"],
            blocking_configs=["pyproject.toml"],
        )
        assert not report.is_safe_to_remove
        assert len(report.blocking_imports) == 1
        assert len(report.blocking_configs) == 1


class TestMoveResult:
    """Tests for MoveResult data model."""
    
    def test_successful_move(self):
        """Test creating a successful move result."""
        result = MoveResult(
            success=True,
            source=Path("doc.md"),
            destination=Path("wiki/doc.md"),
        )
        assert result.success
        assert result.error is None
    
    def test_failed_move(self):
        """Test creating a failed move result."""
        result = MoveResult(
            success=False,
            source=Path("doc.md"),
            destination=Path("wiki/doc.md"),
            error="Permission denied",
        )
        assert not result.success
        assert result.error == "Permission denied"


class TestRemovalResult:
    """Tests for RemovalResult data model."""
    
    def test_successful_removal(self):
        """Test creating a successful removal result."""
        result = RemovalResult(
            success=True,
            file_path=Path("old.py"),
            reason="Obsolete code",
        )
        assert result.success
        assert result.error is None


class TestOperation:
    """Tests for Operation data model."""
    
    def test_move_operation(self):
        """Test creating a move operation."""
        op = Operation(
            type="move",
            file_path=Path("doc.md"),
            destination=Path("wiki/doc.md"),
            reason="Consolidate documentation",
        )
        assert op.type == "move"
        assert op.destination is not None
        assert isinstance(op.timestamp, datetime)
    
    def test_remove_operation(self):
        """Test creating a remove operation."""
        op = Operation(
            type="remove",
            file_path=Path("old.py"),
            reason="Obsolete code",
        )
        assert op.type == "remove"
        assert op.destination is None


class TestCleanupReport:
    """Tests for CleanupReport data model."""
    
    def test_empty_report_markdown(self):
        """Test generating markdown for empty report."""
        report = CleanupReport()
        markdown = report.to_markdown()
        assert "# Workspace Cleanup Report" in markdown
        assert "No files moved to wiki" in markdown
        assert "No files moved to tests" in markdown
        assert "No files removed" in markdown
    
    def test_report_with_operations_markdown(self):
        """Test generating markdown for report with operations."""
        report = CleanupReport(
            moved_to_wiki=[
                Operation(
                    type="move",
                    file_path=Path("doc.md"),
                    destination=Path("wiki/doc.md"),
                )
            ],
            moved_to_tests=[
                Operation(
                    type="move",
                    file_path=Path("test.py"),
                    destination=Path("tests/test.py"),
                )
            ],
            removed_files=[
                Operation(
                    type="remove",
                    file_path=Path("old.py"),
                    reason="Obsolete",
                )
            ],
        )
        markdown = report.to_markdown()
        assert "`doc.md` → `wiki/doc.md`" in markdown
        assert "`test.py` → `tests/test.py`" in markdown
        assert "`old.py` - Obsolete" in markdown
    
    def test_report_with_verification_results(self):
        """Test generating markdown with verification results."""
        report = CleanupReport(
            verification_results=VerificationResults(
                all_imports_valid=True,
                all_links_valid=True,
                pytest_discovery_success=True,
            )
        )
        markdown = report.to_markdown()
        assert "✓ All imports valid" in markdown
        assert "✓ All documentation links valid" in markdown
        assert "✓ Pytest discovery successful" in markdown


# Property-Based Tests
# Feature: workspace-cleanup-reorganization, Property 25: Report Completeness

# Strategy for generating valid filenames
valid_filename_chars = st.characters(
    whitelist_categories=("Lu", "Ll", "Nd"),  # Letters and digits
    whitelist_characters="_-.",
)
valid_filename = st.text(
    alphabet=valid_filename_chars,
    min_size=1,
    max_size=20,
).filter(lambda s: s not in (".", "..") and "/" not in s and "\\" not in s)


@given(
    st.lists(valid_filename, min_size=0, max_size=10),
    st.lists(valid_filename, min_size=0, max_size=10),
    st.lists(valid_filename, min_size=0, max_size=10),
)
def test_property_report_completeness(wiki_files, test_files, removed_files):
    """
    Property 25: Report Completeness
    
    For any file that is moved, removed, or preserved, that file must appear
    in the appropriate section of the cleanup report.
    
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    """
    # Create operations for each file
    moved_to_wiki = [
        Operation(
            type="move",
            file_path=Path(f),
            destination=Path(f"wiki/{f}"),
        )
        for f in wiki_files
    ]
    
    moved_to_tests = [
        Operation(
            type="move",
            file_path=Path(f),
            destination=Path(f"tests/{f}"),
        )
        for f in test_files
    ]
    
    removed = [
        Operation(
            type="remove",
            file_path=Path(f),
            reason="obsolete",
        )
        for f in removed_files
    ]
    
    # Create report
    report = CleanupReport(
        moved_to_wiki=moved_to_wiki,
        moved_to_tests=moved_to_tests,
        removed_files=removed,
    )
    
    # Verify all files appear in report
    markdown = report.to_markdown()
    
    # Check wiki files appear in report
    for f in wiki_files:
        assert f in markdown, f"File {f} moved to wiki must appear in report"
    
    # Check test files appear in report
    for f in test_files:
        assert f in markdown, f"File {f} moved to tests must appear in report"
    
    # Check removed files appear in report
    for f in removed_files:
        assert f in markdown, f"File {f} removed must appear in report"
