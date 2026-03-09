"""Main orchestration script for workspace cleanup."""

import logging
from pathlib import Path
from typing import List, Tuple

from .code_analyzer import CodeAnalyzer
from .dependency_checker import DependencyChecker
from .file_mover import FileMover
from .file_scanner import FileScanner
from .models import (
    CleanupPlan,
    CleanupReport,
    ContentEvaluation,
    FileInventory,
    ObsolescenceReport,
    Operation,
    SafetyReport,
    VerificationResults,
)


logger = logging.getLogger(__name__)


class CleanupOrchestrator:
    """Orchestrates the three-phase workspace cleanup workflow."""
    
    def __init__(self, workspace_root: Path, wiki_dir: Path, tests_dir: Path):
        """Initialize the cleanup orchestrator.
        
        Args:
            workspace_root: Path to the workspace root directory
            wiki_dir: Path to the wiki directory
            tests_dir: Path to the tests directory
        """
        self.workspace_root = workspace_root
        self.wiki_dir = wiki_dir
        self.tests_dir = tests_dir
        
        # Initialize components
        self.scanner = FileScanner(workspace_root)
        self.analyzer = CodeAnalyzer(workspace_root)
        self.checker = DependencyChecker(workspace_root)
        self.mover = FileMover()
    
    def run_cleanup(self, dry_run: bool = False) -> CleanupReport:
        """Execute the complete three-phase cleanup workflow.
        
        Args:
            dry_run: If True, only analyze and plan without executing operations
        
        Returns:
            CleanupReport with results of all operations
        """
        logger.info("Starting workspace cleanup workflow")
        
        # Phase 1: Analysis
        logger.info("Phase 1: Analysis - Scanning workspace")
        inventory = self._phase_1_analysis()
        
        # Phase 2: Validation
        logger.info("Phase 2: Validation - Building and validating cleanup plan")
        plan = self._phase_2_validation(inventory)
        
        # Phase 3: Execution
        if dry_run:
            logger.info("Dry run mode - skipping execution phase")
            report = self._create_dry_run_report(plan)
        else:
            logger.info("Phase 3: Execution - Performing file operations")
            report = self._phase_3_execution(plan)
        
        logger.info("Workspace cleanup workflow completed")
        return report
    
    def _phase_1_analysis(self) -> FileInventory:
        """Phase 1: Scan the workspace and build file inventory.
        
        Returns:
            FileInventory with all categorized files
        """
        inventory = self.scanner.scan_workspace()
        
        logger.info(f"Found {len(inventory.root_documentation)} root documentation files")
        logger.info(f"Found {len(inventory.root_tests_py)} root Python test files")
        logger.info(f"Found {len(inventory.root_tests_html)} root HTML test files")
        logger.info(f"Found {len(inventory.root_tests_db)} root database test files")
        logger.info(f"Found {len(inventory.specs_files)} specs folder files")
        logger.info(f"Protected {len(inventory.protected_files)} files in core directories")
        
        return inventory
    
    def _phase_2_validation(self, inventory: FileInventory) -> CleanupPlan:
        """Phase 2: Analyze files and build validated cleanup plan.
        
        Args:
            inventory: FileInventory from phase 1
        
        Returns:
            Validated CleanupPlan
        
        Raises:
            ValueError: If the cleanup plan has validation errors
        """
        plan = CleanupPlan(
            protected_files=inventory.protected_files,
            workspace_root=self.workspace_root
        )
        
        # Process root documentation files
        for doc_file in inventory.root_documentation:
            dest = self.wiki_dir / doc_file.name
            plan.files_to_move_to_wiki.append((doc_file, dest))
            logger.debug(f"Plan: Move {doc_file} to wiki")
        
        # Process root test files
        for test_file in inventory.root_tests_py + inventory.root_tests_html + inventory.root_tests_db:
            dest = self.tests_dir / test_file.name
            plan.files_to_move_to_tests.append((test_file, dest))
            logger.debug(f"Plan: Move {test_file} to tests")
        
        # Process specs folder files
        for specs_file in inventory.specs_files:
            evaluation = self.analyzer.evaluate_specs_content(specs_file)
            
            if evaluation.recommended_action == "move_to_wiki":
                dest = self.wiki_dir / specs_file.name
                plan.files_to_move_to_wiki.append((specs_file, dest))
                logger.debug(f"Plan: Move {specs_file} to wiki - {evaluation.reason}")
            elif evaluation.recommended_action == "remove":
                # Verify safety before adding to removal list
                safety_report = self.checker.check_import_safety(specs_file)
                if safety_report.is_safe_to_remove:
                    plan.files_to_remove.append((specs_file, evaluation.reason))
                    logger.debug(f"Plan: Remove {specs_file} - {evaluation.reason}")
                else:
                    plan.files_to_preserve.append(specs_file)
                    logger.warning(f"Plan: Preserve {specs_file} - has dependencies")
        
        # Validate the plan
        validation_errors = plan.validate()
        if validation_errors:
            error_msg = "Cleanup plan validation failed:\n" + "\n".join(f"  - {err}" for err in validation_errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"Plan validated: {len(plan.files_to_move_to_wiki)} to wiki, "
                   f"{len(plan.files_to_move_to_tests)} to tests, "
                   f"{len(plan.files_to_remove)} to remove, "
                   f"{len(plan.files_to_preserve)} to preserve")
        
        return plan
    
    def _phase_3_execution(self, plan: CleanupPlan) -> CleanupReport:
        """Phase 3: Execute file operations and verify results.
        
        Args:
            plan: Validated CleanupPlan from phase 2
        
        Returns:
            CleanupReport with results of all operations
        """
        report = CleanupReport()
        
        # Execute moves to wiki
        for source, dest in plan.files_to_move_to_wiki:
            result = self.mover.move_file(source, dest)
            if result.success:
                op = Operation(type="move", file_path=source, destination=dest, reason="Documentation consolidation")
                report.moved_to_wiki.append(op)
                logger.info(f"Moved {source} to {dest}")
            else:
                logger.error(f"Failed to move {source} to {dest}: {result.error}")
        
        # Execute moves to tests
        for source, dest in plan.files_to_move_to_tests:
            result = self.mover.move_file(source, dest)
            if result.success:
                op = Operation(type="move", file_path=source, destination=dest, reason="Test consolidation")
                report.moved_to_tests.append(op)
                logger.info(f"Moved {source} to {dest}")
            else:
                logger.error(f"Failed to move {source} to {dest}: {result.error}")
        
        # Execute removals
        for file_path, reason in plan.files_to_remove:
            result = self.mover.remove_file(file_path, reason)
            if result.success:
                op = Operation(type="remove", file_path=file_path, reason=reason)
                report.removed_files.append(op)
                logger.info(f"Removed {file_path}: {reason}")
            else:
                logger.error(f"Failed to remove {file_path}: {result.error}")
        
        # Record preserved files
        report.preserved_files = plan.files_to_preserve
        
        # Run verification checks
        logger.info("Running post-execution verification")
        report.verification_results = self._run_verification()
        
        # Generate and save report
        report_path = self.wiki_dir / "WORKSPACE_CLEANUP_REPORT.md"
        self.mover.generate_cleanup_report(report, report_path)
        logger.info(f"Cleanup report saved to {report_path}")
        
        return report
    
    def _run_verification(self) -> VerificationResults:
        """Run post-execution verification checks.
        
        Returns:
            VerificationResults with all verification outcomes
        """
        results = VerificationResults()
        
        # Verify test imports
        test_files = list(self.tests_dir.glob("test_*.py"))
        if test_files:
            import_verification = self.checker.verify_test_imports(test_files)
            results.all_imports_valid = import_verification.all_imports_valid
            results.broken_imports = import_verification.broken_imports
            
            if not results.all_imports_valid:
                logger.warning(f"Found {len(results.broken_imports)} broken imports")
        
        # Verify documentation links
        wiki_files = list(self.wiki_dir.glob("*.md"))
        for wiki_file in wiki_files:
            broken_links = self.checker.check_documentation_links(wiki_file)
            if broken_links:
                results.all_links_valid = False
                for link in broken_links:
                    results.broken_links.append((wiki_file, link))
                logger.warning(f"Found broken links in {wiki_file}")
        
        # Verify pytest discovery
        discovery_report = self.checker.verify_pytest_discovery()
        results.pytest_discovery_success = discovery_report.discovery_successful
        results.pytest_errors = discovery_report.errors
        
        if not results.pytest_discovery_success:
            logger.warning(f"Pytest discovery issues: {len(results.pytest_errors)} errors")
        
        return results
    
    def _create_dry_run_report(self, plan: CleanupPlan) -> CleanupReport:
        """Create a report for dry run mode without executing operations.
        
        Args:
            plan: CleanupPlan to report on
        
        Returns:
            CleanupReport showing planned operations
        """
        report = CleanupReport()
        
        # Convert plan to report operations (without executing)
        for source, dest in plan.files_to_move_to_wiki:
            op = Operation(type="move", file_path=source, destination=dest, reason="Documentation consolidation (planned)")
            report.moved_to_wiki.append(op)
        
        for source, dest in plan.files_to_move_to_tests:
            op = Operation(type="move", file_path=source, destination=dest, reason="Test consolidation (planned)")
            report.moved_to_tests.append(op)
        
        for file_path, reason in plan.files_to_remove:
            op = Operation(type="remove", file_path=file_path, reason=f"{reason} (planned)")
            report.removed_files.append(op)
        
        report.preserved_files = plan.files_to_preserve
        
        return report
