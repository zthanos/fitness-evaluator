# Implementation Plan: Workspace Cleanup and Reorganization

## Overview

This implementation plan breaks down the workspace cleanup system into discrete coding tasks. The system will consolidate 60+ test files, move documentation to wiki/, evaluate legacy specs/ content, and safely remove obsolete code. The implementation follows a three-phase approach: Analysis, Validation, and Execution, with comprehensive property-based testing using Hypothesis.

## Tasks

- [x] 1. Set up project structure and core data models
  - Create workspace_cleanup/ directory in scripts/
  - Define data classes: FileInventory, CleanupPlan, CleanupReport, ObsolescenceReport, ContentEvaluation, SafetyReport
  - Define result classes: MoveResult, RemovalResult, Operation
  - Set up Hypothesis for property-based testing
  - _Requirements: 1.1-1.7, 2.1-2.7, 3.1-3.7_

- [x]* 1.1 Write property test for data model integrity
  - **Property 25: Report Completeness**
  - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

- [ ] 2. Implement File Scanner component
  - [x] 2.1 Create FileScanner class with pathlib-based file discovery
    - Implement scan_root_documentation() to find markdown files in workspace root
    - Implement scan_root_tests() to find test_*.py, test_*.html, test_*.db files
    - Implement scan_specs_folder() to find files in specs/ directory
    - Implement get_protected_directories() returning app/, alembic/, public/, scripts/, .kiro/specs/
    - Filter out hidden directories (.git, .venv, __pycache__)
    - _Requirements: 1.1-1.5, 2.1-2.2, 3.1-3.3_

  - [ ]* 2.2 Write property test for file pattern matching
    - **Property 2: Test File Pattern Matching**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 2.3 Write property test for protected directory preservation
    - **Property 18: Protected Directory Preservation**
    - **Validates: Requirements 5.7, 6.1, 6.2, 6.3, 6.4, 6.5**

  - [ ]* 2.4 Write unit tests for FileScanner edge cases
    - Test handling of empty directories
    - Test handling of symbolic links
    - Test filtering of hidden directories
    - _Requirements: 1.1-1.5, 3.1-3.3_

- [ ] 3. Implement Code Analyzer component
  - [x] 3.1 Create CodeAnalyzer class with obsolescence detection
    - Implement analyze_test_file() using AST parsing to detect obsolete tests
    - Detect duplicate functionality by comparing test function names and imports
    - Detect removed features by checking if tested modules exist in app/
    - Detect temporary files by checking for "debug", "temp", "scratch", "tmp" in filenames
    - Detect superseded tests by comparing timestamps and naming patterns
    - Return ObsolescenceReport with confidence scores
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7_

  - [x] 3.2 Implement specs content evaluation
    - Implement evaluate_specs_content() to parse markdown structure
    - Check for unique technical content vs. boilerplate
    - Verify if content is already covered in .kiro/specs/ or wiki/
    - Classify as "valuable", "obsolete", or "duplicate"
    - Return ContentEvaluation with recommended action
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 3.3 Implement duplicate test detection
    - Implement find_duplicate_tests() to identify test files with duplicate functionality
    - Compare test function names across files
    - Compare import statements for similarity
    - Return list of DuplicateGroup objects
    - _Requirements: 4.1_

  - [ ]* 3.4 Write property test for obsolescence justification
    - **Property 11: Obsolescence Justification**
    - **Validates: Requirements 4.5**

  - [ ]* 3.5 Write property test for obsolescence report completeness
    - **Property 12: Obsolescence Report Completeness**
    - **Validates: Requirements 4.6**

  - [ ]* 3.6 Write property test for active test exclusion
    - **Property 13: Active Test Exclusion**
    - **Validates: Requirements 4.7**

  - [ ]* 3.7 Write unit tests for CodeAnalyzer
    - Test duplicate detection with known duplicate files
    - Test removed feature detection with missing modules
    - Test temporary file detection with various naming patterns
    - Test superseded test detection with timestamp comparisons
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Dependency Checker component
  - [x] 5.1 Create DependencyChecker class with import analysis
    - Implement check_import_safety() using AST parsing to find imports in app/
    - Implement check_config_references() to scan pyproject.toml, alembic.ini, docker-compose.yml
    - Implement check_documentation_links() to parse markdown files for relative links
    - Return SafetyReport with blocking imports, configs, and docs
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 5.2 Implement test import verification
    - Implement verify_test_imports() to check import resolution after moving tests
    - Detect relative imports that need updating (e.g., from test_helper import fixture)
    - Return ImportVerification with broken imports list
    - _Requirements: 3.7, 7.2_

  - [x] 5.3 Implement pytest discovery verification
    - Implement verify_pytest_discovery() to check if pytest can discover all tests in tests/
    - Run pytest --collect-only programmatically
    - Return DiscoveryReport with discovery results
    - _Requirements: 7.5_

  - [ ]* 5.4 Write property test for dependency-free removal
    - **Property 14: Dependency-Free Removal**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 5.5 Write property test for safety classification
    - **Property 15: Safety Classification**
    - **Validates: Requirements 5.4**

  - [ ]* 5.6 Write property test for verified removal only
    - **Property 16: Verified Removal Only**
    - **Validates: Requirements 5.5**

  - [ ]* 5.7 Write property test for import resolution after move
    - **Property 4: Import Resolution After Move**
    - **Validates: Requirements 3.7, 7.2**

  - [ ]* 5.8 Write property test for core application import integrity
    - **Property 19: Core Application Import Integrity**
    - **Validates: Requirements 7.1**

  - [ ]* 5.9 Write property test for documentation link integrity
    - **Property 20: Documentation Link Integrity**
    - **Validates: Requirements 7.3**

  - [ ]* 5.10 Write property test for pytest discovery verification
    - **Property 22: Pytest Discovery Verification**
    - **Validates: Requirements 7.5**

  - [ ]* 5.11 Write unit tests for DependencyChecker
    - Test import safety with known import patterns
    - Test config reference detection with sample config files
    - Test documentation link parsing with sample markdown
    - Test pytest discovery with sample test structure
    - _Requirements: 5.1, 5.2, 5.3, 7.2, 7.5_

- [ ] 6. Implement File Mover component
  - [x] 6.1 Create FileMover class with atomic file operations
    - Implement move_file() using shutil.move() with verification
    - Verify source exists before moving
    - Verify destination doesn't exist (avoid overwrites)
    - Verify file exists at destination after move
    - Preserve file permissions
    - Return MoveResult with success status
    - _Requirements: 1.6, 1.7, 3.5, 3.6, 7.7_

  - [x] 6.2 Implement safe file removal
    - Implement remove_file() using Path.unlink()
    - Log file path and reason before removal
    - Only remove files verified safe by DependencyChecker
    - Remove empty directories after file removal
    - Return RemovalResult with success status
    - _Requirements: 2.5, 2.6, 2.7, 5.5, 5.6_

  - [x] 6.3 Implement cleanup report generation
    - Implement generate_cleanup_report() to create markdown report
    - Include sections: moved to wiki, moved to tests, removed files, preserved files
    - Include original and destination paths for moved files
    - Include justifications for removed files
    - Include verification results
    - Save report to wiki/WORKSPACE_CLEANUP_REPORT.md
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [ ]* 6.4 Write property test for move operation atomicity
    - **Property 1: Move Operation Atomicity**
    - **Validates: Requirements 1.6, 1.7, 3.6**

  - [ ]* 6.5 Write property test for file name preservation
    - **Property 3: File Name Preservation**
    - **Validates: Requirements 3.5**

  - [ ]* 6.6 Write property test for empty directory cleanup
    - **Property 5: Empty Directory Cleanup**
    - **Validates: Requirements 2.7**

  - [ ]* 6.7 Write property test for existing structure preservation
    - **Property 6: Existing Structure Preservation**
    - **Validates: Requirements 3.4, 6.6, 6.7**

  - [ ]* 6.8 Write property test for removal logging
    - **Property 17: Removal Logging**
    - **Validates: Requirements 5.6**

  - [ ]* 6.9 Write property test for permission preservation
    - **Property 24: Permission Preservation**
    - **Validates: Requirements 7.7**

  - [ ]* 6.10 Write property test for report detail sufficiency
    - **Property 26: Report Detail Sufficiency**
    - **Validates: Requirements 8.5, 8.6**

  - [ ]* 6.11 Write unit tests for FileMover
    - Test move operation with various file types
    - Test handling of permission denied errors
    - Test handling of missing source files
    - Test handling of existing destination files
    - Test empty directory removal
    - Test report generation formatting
    - _Requirements: 1.6, 1.7, 2.7, 3.5, 3.6, 8.1-8.7_

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement error handling and recovery
  - [x] 8.1 Add error handling to FileMover operations
    - Handle source file doesn't exist: log error, skip file, continue
    - Handle destination file already exists: log error, skip file, continue
    - Handle destination directory doesn't exist: create directory, retry
    - Handle permission denied: log error, mark for manual intervention, continue
    - Handle file locked: log error, mark for manual intervention, continue
    - Collect all errors for reporting
    - _Requirements: 1.6, 1.7, 3.6_

  - [x] 8.2 Add error handling to CodeAnalyzer
    - Handle file cannot be read: log error, mark as "preserve"
    - Handle binary file: log warning, mark as "preserve"
    - Handle parsing fails: log error, mark as "preserve"
    - Handle AST parsing fails: log error, mark for manual review
    - Conservative approach: when in doubt, preserve the file
    - _Requirements: 4.5, 4.6_

  - [x] 8.3 Add error handling to DependencyChecker
    - Handle AST parsing fails: log error, mark file as requiring manual review
    - Handle module not found: record as broken import for reporting
    - Handle config file malformed: log error, skip that config, continue
    - Handle config file doesn't exist: log warning, continue
    - Fallback: mark as "not safe to remove" when checking fails
    - _Requirements: 5.4, 5.5, 7.4_

  - [ ]* 8.4 Write unit tests for error handling
    - Test handling of missing files
    - Test handling of permission errors
    - Test handling of malformed config files
    - Test handling of AST parsing failures
    - Test error collection and reporting
    - _Requirements: 5.4, 7.4_

- [x] 9. Implement main orchestration and cleanup plan
  - [x] 9.1 Create CleanupPlan class with validation
    - Implement validate() to check for conflicts
    - Check no file appears in multiple operation lists
    - Check all destination directories exist or can be created
    - Check no protected files are in operation lists
    - Return list of validation errors
    - _Requirements: 5.7, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 9.2 Create main orchestration script
    - Implement three-phase workflow: Analysis, Validation, Execution
    - Phase 1: Run FileScanner to build FileInventory
    - Phase 2: Run CodeAnalyzer to identify obsolete files and evaluate specs content
    - Phase 3: Run DependencyChecker to verify safety of all operations
    - Build CleanupPlan from analysis results
    - Validate CleanupPlan before execution
    - Execute FileMover operations if plan is valid
    - Run verification checks after execution
    - Generate and save cleanup report
    - _Requirements: 1.1-1.7, 2.1-2.7, 3.1-3.7, 4.1-4.7, 5.1-5.7, 6.1-6.7, 7.1-7.7, 8.1-8.7_

  - [ ]* 9.3 Write property test for breaking change reporting
    - **Property 21: Breaking Change Reporting**
    - **Validates: Requirements 7.4**

  - [ ]* 9.4 Write property test for orphaned database detection
    - **Property 23: Orphaned Database Detection**
    - **Validates: Requirements 7.6**

  - [ ]* 9.5 Write integration tests for full cleanup workflow
    - Create temporary test workspace with known structure
    - Run full cleanup workflow
    - Verify all expected moves occurred
    - Verify all expected removals occurred
    - Verify report accuracy
    - Verify no breaking changes
    - _Requirements: 1.1-1.7, 2.1-2.7, 3.1-3.7, 7.1-7.7, 8.1-8.7_

- [ ] 10. Add remaining property-based tests
  - [ ]* 10.1 Write property test for duplicate detection capability
    - **Property 7: Duplicate Detection Capability**
    - **Validates: Requirements 4.1**

  - [ ]* 10.2 Write property test for removed feature detection
    - **Property 8: Removed Feature Detection**
    - **Validates: Requirements 4.2**

  - [ ]* 10.3 Write property test for temporary file detection
    - **Property 9: Temporary File Detection**
    - **Validates: Requirements 4.3**

  - [ ]* 10.4 Write property test for superseded test detection
    - **Property 10: Superseded Test Detection**
    - **Validates: Requirements 4.4**

- [x] 11. Final checkpoint and documentation
  - [x] 11.1 Run full test suite and verify all tests pass
    - Run all unit tests
    - Run all property-based tests (minimum 100 iterations each)
    - Verify test coverage for all components
    - _Requirements: All_

  - [x] 11.2 Create CLI interface for running cleanup
    - Add command-line arguments for dry-run mode
    - Add command-line arguments for verbose logging
    - Add command-line arguments for specifying workspace path
    - Add help text and usage examples
    - _Requirements: All_

  - [x] 11.3 Add logging configuration
    - Configure logging to file and console
    - Add log levels for different operation types
    - Add timestamps to all log entries
    - _Requirements: 5.6, 8.1-8.7_

  - [x] 11.4 Final checkpoint - Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property-based tests use Hypothesis with minimum 100 iterations
- All property tests are tagged with feature name and property number
- Conservative approach: when in doubt, preserve files rather than remove them
- No automatic rollback implemented (too risky for file operations)
- Manual verification recommended after automated cleanup completes
