"""Tests for cleanup orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from .cleanup_orchestrator import CleanupOrchestrator
from .models import (
    CleanupPlan,
    CleanupReport,
    ContentEvaluation,
    FileInventory,
    MoveResult,
    RemovalResult,
    SafetyReport,
    VerificationResults,
    ImportVerification,
    DiscoveryReport,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace structure."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    # Create directories
    (workspace / "wiki").mkdir()
    (workspace / "tests").mkdir()
    (workspace / "app").mkdir()
    (workspace / "specs").mkdir()
    
    # Create some test files
    (workspace / "README.md").write_text("# Project")
    (workspace / "test_example.py").write_text("def test_foo(): pass")
    (workspace / "specs" / "plan.md").write_text("# Plan")
    
    return workspace


@pytest.fixture
def orchestrator(temp_workspace):
    """Create a cleanup orchestrator instance."""
    wiki_dir = temp_workspace / "wiki"
    tests_dir = temp_workspace / "tests"
    return CleanupOrchestrator(temp_workspace, wiki_dir, tests_dir)


def test_orchestrator_initialization(orchestrator, temp_workspace):
    """Test that orchestrator initializes correctly."""
    assert orchestrator.workspace_root == temp_workspace
    assert orchestrator.wiki_dir == temp_workspace / "wiki"
    assert orchestrator.tests_dir == temp_workspace / "tests"
    assert orchestrator.scanner is not None
    assert orchestrator.analyzer is not None
    assert orchestrator.checker is not None
    assert orchestrator.mover is not None


def test_phase_1_analysis(orchestrator):
    """Test phase 1 analysis scans workspace correctly."""
    inventory = orchestrator._phase_1_analysis()
    
    assert isinstance(inventory, FileInventory)
    assert len(inventory.root_documentation) > 0  # Should find README.md
    assert len(inventory.root_tests_py) > 0  # Should find test_example.py


def test_phase_2_validation_creates_plan(orchestrator):
    """Test phase 2 creates and validates cleanup plan."""
    # Create a simple inventory
    inventory = FileInventory()
    inventory.root_documentation = [orchestrator.workspace_root / "README.md"]
    inventory.root_tests_py = [orchestrator.workspace_root / "test_example.py"]
    inventory.specs_files = [orchestrator.workspace_root / "specs" / "plan.md"]
    inventory.protected_files = set()
    
    # Mock the analyzer to return a simple evaluation
    with patch.object(orchestrator.analyzer, 'evaluate_specs_content') as mock_eval:
        mock_eval.return_value = ContentEvaluation(
            file_path=Path("specs/plan.md"),
            has_value=True,
            reason="Contains valuable content",
            recommended_action="move_to_wiki"
        )
        
        plan = orchestrator._phase_2_validation(inventory)
    
    assert isinstance(plan, CleanupPlan)
    assert len(plan.files_to_move_to_wiki) > 0
    assert len(plan.files_to_move_to_tests) > 0


def test_phase_2_validation_checks_safety_before_removal(orchestrator):
    """Test phase 2 checks safety before adding files to removal list."""
    inventory = FileInventory()
    inventory.specs_files = [orchestrator.workspace_root / "specs" / "plan.md"]
    inventory.protected_files = set()
    
    # Mock analyzer to recommend removal
    with patch.object(orchestrator.analyzer, 'evaluate_specs_content') as mock_eval, \
         patch.object(orchestrator.checker, 'check_import_safety') as mock_safety:
        
        mock_eval.return_value = ContentEvaluation(
            file_path=Path("specs/plan.md"),
            has_value=False,
            reason="Obsolete content",
            recommended_action="remove"
        )
        
        # Test case 1: Safe to remove
        mock_safety.return_value = SafetyReport(
            file_path=Path("specs/plan.md"),
            is_safe_to_remove=True
        )
        
        plan = orchestrator._phase_2_validation(inventory)
        assert len(plan.files_to_remove) == 1
        assert len(plan.files_to_preserve) == 0
        
        # Test case 2: Not safe to remove
        mock_safety.return_value = SafetyReport(
            file_path=Path("specs/plan.md"),
            is_safe_to_remove=False,
            blocking_imports=["app.models"]
        )
        
        plan = orchestrator._phase_2_validation(inventory)
        assert len(plan.files_to_remove) == 0
        assert len(plan.files_to_preserve) == 1


def test_phase_2_validation_fails_on_invalid_plan(orchestrator):
    """Test phase 2 raises error if plan validation fails."""
    inventory = FileInventory()
    # Create a scenario that would cause validation error
    # (e.g., file in protected directory)
    protected_file = orchestrator.workspace_root / "app" / "models.py"
    protected_file.parent.mkdir(exist_ok=True)
    protected_file.write_text("# Model")
    
    inventory.root_documentation = [protected_file]  # Try to move protected file
    inventory.protected_files = {protected_file}
    
    with pytest.raises(ValueError, match="validation failed"):
        orchestrator._phase_2_validation(inventory)


def test_phase_3_execution_moves_files(orchestrator):
    """Test phase 3 executes file moves correctly."""
    source = orchestrator.workspace_root / "README.md"
    dest = orchestrator.wiki_dir / "README.md"
    
    plan = CleanupPlan()
    plan.files_to_move_to_wiki = [(source, dest)]
    
    with patch.object(orchestrator.mover, 'move_file') as mock_move, \
         patch.object(orchestrator.mover, 'generate_cleanup_report') as mock_report, \
         patch.object(orchestrator, '_run_verification') as mock_verify:
        
        mock_move.return_value = MoveResult(success=True, source=source, destination=dest)
        mock_verify.return_value = VerificationResults()
        
        report = orchestrator._phase_3_execution(plan)
    
    assert len(report.moved_to_wiki) == 1
    assert report.moved_to_wiki[0].file_path == source
    assert report.moved_to_wiki[0].destination == dest
    mock_move.assert_called_once_with(source, dest)


def test_phase_3_execution_removes_files(orchestrator):
    """Test phase 3 executes file removals correctly."""
    file_to_remove = orchestrator.workspace_root / "obsolete.py"
    reason = "Obsolete test file"
    
    plan = CleanupPlan()
    plan.files_to_remove = [(file_to_remove, reason)]
    
    with patch.object(orchestrator.mover, 'remove_file') as mock_remove, \
         patch.object(orchestrator.mover, 'generate_cleanup_report') as mock_report, \
         patch.object(orchestrator, '_run_verification') as mock_verify:
        
        mock_remove.return_value = RemovalResult(success=True, file_path=file_to_remove, reason=reason)
        mock_verify.return_value = VerificationResults()
        
        report = orchestrator._phase_3_execution(plan)
    
    assert len(report.removed_files) == 1
    assert report.removed_files[0].file_path == file_to_remove
    assert report.removed_files[0].reason == reason
    mock_remove.assert_called_once_with(file_to_remove, reason)


def test_run_verification_checks_imports(orchestrator):
    """Test verification checks test imports."""
    # Create a test file
    test_file = orchestrator.tests_dir / "test_example.py"
    test_file.write_text("def test_foo(): pass")
    
    with patch.object(orchestrator.checker, 'verify_test_imports') as mock_verify, \
         patch.object(orchestrator.checker, 'check_documentation_links') as mock_links, \
         patch.object(orchestrator.checker, 'verify_pytest_discovery') as mock_pytest:
        
        mock_verify.return_value = ImportVerification(
            all_imports_valid=True,
            broken_imports=[]
        )
        mock_links.return_value = []
        mock_pytest.return_value = DiscoveryReport(
            discovery_successful=True,
            discovered_tests=["test_example.py::test_foo"],
            total_collected=1
        )
        
        results = orchestrator._run_verification()
    
    assert results.all_imports_valid is True
    assert results.all_links_valid is True
    assert results.pytest_discovery_success is True
    mock_verify.assert_called_once()


def test_run_verification_detects_broken_imports(orchestrator):
    """Test verification detects broken imports."""
    test_file = orchestrator.tests_dir / "test_example.py"
    test_file.write_text("from missing_module import foo")
    
    with patch.object(orchestrator.checker, 'verify_test_imports') as mock_verify, \
         patch.object(orchestrator.checker, 'check_documentation_links') as mock_links, \
         patch.object(orchestrator.checker, 'verify_pytest_discovery') as mock_pytest:
        
        mock_verify.return_value = ImportVerification(
            all_imports_valid=False,
            broken_imports=[(test_file, "from missing_module import foo")]
        )
        mock_links.return_value = []
        mock_pytest.return_value = DiscoveryReport(discovery_successful=True)
        
        results = orchestrator._run_verification()
    
    assert results.all_imports_valid is False
    assert len(results.broken_imports) == 1


def test_dry_run_mode_does_not_execute(orchestrator):
    """Test dry run mode creates report without executing operations."""
    with patch.object(orchestrator, '_phase_1_analysis') as mock_phase1, \
         patch.object(orchestrator, '_phase_2_validation') as mock_phase2, \
         patch.object(orchestrator, '_phase_3_execution') as mock_phase3, \
         patch.object(orchestrator, '_create_dry_run_report') as mock_dry_run:
        
        mock_phase1.return_value = FileInventory()
        mock_phase2.return_value = CleanupPlan()
        mock_dry_run.return_value = CleanupReport()
        
        report = orchestrator.run_cleanup(dry_run=True)
    
    # Phase 3 should not be called in dry run mode
    mock_phase3.assert_not_called()
    mock_dry_run.assert_called_once()


def test_create_dry_run_report(orchestrator):
    """Test dry run report creation."""
    source = orchestrator.workspace_root / "README.md"
    dest = orchestrator.wiki_dir / "README.md"
    
    plan = CleanupPlan()
    plan.files_to_move_to_wiki = [(source, dest)]
    plan.files_to_remove = [(source, "Test reason")]
    plan.files_to_preserve = [orchestrator.workspace_root / "keep.py"]
    
    report = orchestrator._create_dry_run_report(plan)
    
    assert len(report.moved_to_wiki) == 1
    assert "(planned)" in report.moved_to_wiki[0].reason
    assert len(report.removed_files) == 1
    assert "(planned)" in report.removed_files[0].reason
    assert len(report.preserved_files) == 1


def test_full_workflow_integration(orchestrator):
    """Test complete workflow from analysis to execution."""
    with patch.object(orchestrator.mover, 'move_file') as mock_move, \
         patch.object(orchestrator.mover, 'remove_file') as mock_remove, \
         patch.object(orchestrator.mover, 'generate_cleanup_report') as mock_report, \
         patch.object(orchestrator.analyzer, 'evaluate_specs_content') as mock_eval, \
         patch.object(orchestrator.checker, 'check_import_safety') as mock_safety, \
         patch.object(orchestrator.checker, 'verify_test_imports') as mock_verify, \
         patch.object(orchestrator.checker, 'check_documentation_links') as mock_links, \
         patch.object(orchestrator.checker, 'verify_pytest_discovery') as mock_pytest:
        
        # Setup mocks
        mock_move.return_value = MoveResult(success=True, source=Path("src"), destination=Path("dest"))
        mock_remove.return_value = RemovalResult(success=True, file_path=Path("file"), reason="test")
        mock_eval.return_value = ContentEvaluation(
            file_path=Path("specs/plan.md"),
            has_value=False,
            reason="Empty",
            recommended_action="remove"
        )
        mock_safety.return_value = SafetyReport(file_path=Path("file"), is_safe_to_remove=True)
        mock_verify.return_value = ImportVerification(all_imports_valid=True)
        mock_links.return_value = []
        mock_pytest.return_value = DiscoveryReport(discovery_successful=True)
        
        # Run full workflow
        report = orchestrator.run_cleanup(dry_run=False)
    
    assert isinstance(report, CleanupReport)
    assert report.verification_results is not None
