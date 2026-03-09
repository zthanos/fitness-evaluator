# Workspace Cleanup and Reorganization

A comprehensive system for cleaning up and reorganizing workspace files, including consolidating test files, moving documentation, evaluating legacy content, and safely removing obsolete code.

## Features

- **Test File Consolidation**: Automatically moves all test files (`test_*.py`, `test_*.html`, `test_*.db`) from the workspace root to the `tests/` directory
- **Documentation Organization**: Moves markdown documentation files to the `wiki/` directory
- **Legacy Content Evaluation**: Analyzes files in the `specs/` folder to determine if they contain valuable content
- **Safe Obsolete Code Removal**: Identifies and removes obsolete code only after verifying no dependencies exist
- **Comprehensive Reporting**: Generates detailed reports of all operations performed
- **Dry Run Mode**: Preview changes without modifying any files
- **Dependency Checking**: Verifies that no breaking changes occur during cleanup

## Installation

The workspace cleanup system is part of the main project. No additional installation is required.

## Usage

### Basic Usage

Run cleanup in the current workspace:

```bash
python -m scripts.workspace_cleanup.run_cleanup
```

### Dry Run Mode

Preview what changes would be made without actually modifying files:

```bash
python -m scripts.workspace_cleanup.run_cleanup --dry-run
```

### Verbose Logging

Enable detailed debug logging:

```bash
python -m scripts.workspace_cleanup.run_cleanup --verbose
```

### Custom Workspace Path

Specify a custom workspace directory:

```bash
python -m scripts.workspace_cleanup.run_cleanup --workspace /path/to/workspace
```

### Combined Options

You can combine multiple options:

```bash
python -m scripts.workspace_cleanup.run_cleanup --dry-run --verbose --workspace /path/to/workspace
```

## Command-Line Options

- `--workspace PATH`: Path to workspace root directory (default: repository root)
- `--wiki PATH`: Path to wiki directory (default: `<workspace>/wiki`)
- `--tests PATH`: Path to tests directory (default: `<workspace>/tests`)
- `--dry-run`: Analyze and plan without executing file operations
- `--verbose`, `-v`: Enable verbose logging (DEBUG level)
- `--help`, `-h`: Show help message and exit

## Output

### Console Output

The script provides real-time logging to the console showing:
- Files being scanned
- Analysis results
- Validation checks
- File operations (moves, removals)
- Verification results
- Summary statistics

### Log File

All operations are logged to `workspace_cleanup.log` in the current directory with timestamps.

### Cleanup Report

A detailed markdown report is generated at `wiki/WORKSPACE_CLEANUP_REPORT.md` containing:
- List of files moved to wiki
- List of files moved to tests
- List of files removed (with justifications)
- List of files preserved
- Verification results
- Any errors or warnings

## Safety Features

The cleanup system includes multiple safety mechanisms:

1. **Protected Directories**: Never modifies files in `app/`, `alembic/`, `public/`, `scripts/`, or `.kiro/specs/`
2. **Dependency Checking**: Verifies files are not imported by core application before removal
3. **Configuration Scanning**: Checks for references in config files before removal
4. **Documentation Link Checking**: Verifies documentation links remain valid after moves
5. **Import Verification**: Ensures all imports resolve correctly after moving test files
6. **Pytest Discovery**: Verifies pytest can discover all tests after reorganization
7. **Conservative Approach**: When in doubt, preserves files rather than removing them

## Architecture

The system consists of four main components:

1. **File Scanner**: Discovers and categorizes files in the workspace
2. **Code Analyzer**: Identifies obsolete code and evaluates content value
3. **Dependency Checker**: Verifies import statements, references, and test discovery
4. **File Mover**: Executes file operations and generates reports

## Testing

The system includes comprehensive test coverage:

```bash
# Run all tests
python -m pytest scripts/workspace_cleanup/ -v

# Run with coverage
python -m pytest scripts/workspace_cleanup/ --cov=scripts.workspace_cleanup --cov-report=html
```

All 113 tests include:
- Unit tests for each component
- Integration tests for the full workflow
- Property-based tests using Hypothesis
- Edge case handling tests
- Error handling tests

## Examples

### Example 1: Preview Changes

```bash
python -m scripts.workspace_cleanup.run_cleanup --dry-run --verbose
```

This will show you exactly what would be done without making any changes.

### Example 2: Clean Up Current Workspace

```bash
python -m scripts.workspace_cleanup.run_cleanup
```

This will perform the cleanup and generate a report at `wiki/WORKSPACE_CLEANUP_REPORT.md`.

### Example 3: Clean Up with Custom Paths

```bash
python -m scripts.workspace_cleanup.run_cleanup \
  --workspace /path/to/project \
  --wiki /path/to/project/documentation \
  --tests /path/to/project/test_suite
```

## Troubleshooting

### Permission Errors

If you encounter permission errors, the script will:
- Log the error
- Mark the file for manual intervention
- Continue with other operations
- List all files requiring manual intervention in the report

### Import Errors After Cleanup

If tests fail to import after cleanup:
1. Check the cleanup report for broken imports
2. Review the `verification_results` section
3. The script should have detected these before making changes

### Files Not Being Removed

The script is conservative and will not remove files if:
- They are imported by the core application
- They are referenced in configuration files
- They are linked in documentation
- Analysis fails or is uncertain

## Contributing

When modifying the workspace cleanup system:

1. Run all tests to ensure nothing breaks
2. Add tests for new functionality
3. Update this README if adding new features
4. Follow the existing code style and patterns

## License

This is part of the main project and follows the same license.
