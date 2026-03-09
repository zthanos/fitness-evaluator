"""Dependency checker for workspace cleanup system."""

import ast
import logging
import re
import sys
from pathlib import Path
from typing import List, Tuple

from .models import SafetyReport, ImportVerification, DiscoveryReport

logger = logging.getLogger(__name__)


class DependencyChecker:
    """Verifies that file operations will not break the application or tests."""
    
    def __init__(self, workspace_root: Path):
        """Initialize the dependency checker.
        
        Args:
            workspace_root: Path to the workspace root directory
        """
        self.workspace_root = workspace_root
        self.app_dir = workspace_root / 'app'
        self.wiki_dir = workspace_root / 'wiki'
    
    def check_import_safety(self, file_path: Path) -> SafetyReport:
        """Verify file is not imported by core application.
        
        Uses AST parsing to find all import statements in app/ that reference
        the given file. This ensures we don't remove files that are actively
        used by the application.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            SafetyReport indicating if file is safe to remove
            
        Error Handling:
            - AST parsing fails: log error, mark file as requiring manual review (not safe to remove)
            - Module not found: record as broken import for reporting
            - File cannot be read: skip file, continue
        """
        blocking_imports = []
        
        # Only check if app/ directory exists
        if not self.app_dir.exists():
            # If app/ doesn't exist, no imports to check
            return SafetyReport(
                file_path=file_path,
                is_safe_to_remove=True,
                blocking_imports=[],
                blocking_configs=[],
                blocking_docs=[]
            )
        
        # Get the module name that would be used to import this file
        # For example: test_foo.py -> test_foo
        module_name = file_path.stem
        
        # Search all Python files in app/ for imports of this file
        try:
            for py_file in self.app_dir.rglob('*.py'):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                except FileNotFoundError:
                    # Skip files that don't exist
                    logger.debug(f"File not found, skipping: {py_file}")
                    continue
                except PermissionError:
                    # Skip files we can't read
                    logger.debug(f"Permission denied, skipping: {py_file}")
                    continue
                except UnicodeDecodeError:
                    # Skip binary files
                    logger.debug(f"Binary file or encoding issue, skipping: {py_file}")
                    continue
                except OSError as e:
                    # Skip files with other read errors
                    logger.debug(f"Error reading file {py_file}: {e}")
                    continue
                
                # Parse the file with AST
                try:
                    tree = ast.parse(content, filename=str(py_file))
                except SyntaxError as e:
                    # Handle AST parsing fails: log error, mark file as requiring manual review
                    error_msg = f"Syntax error parsing {py_file}: {e}"
                    logger.error(error_msg)
                    # Don't mark as safe to remove if we can't parse files in app/
                    blocking_imports.append(f"{py_file.relative_to(self.workspace_root)}: AST parsing failed (requires manual review)")
                    continue
                except ValueError as e:
                    # Handle AST parsing fails: log error, mark file as requiring manual review
                    error_msg = f"AST parsing failed for {py_file}: {e}"
                    logger.error(error_msg)
                    blocking_imports.append(f"{py_file.relative_to(self.workspace_root)}: AST parsing failed (requires manual review)")
                    continue
                except Exception as e:
                    # Handle unexpected parsing errors
                    error_msg = f"Unexpected error parsing {py_file}: {e}"
                    logger.error(error_msg)
                    blocking_imports.append(f"{py_file.relative_to(self.workspace_root)}: Unexpected parsing error (requires manual review)")
                    continue
                
                # Check all import statements
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            # Check if this imports our file
                            if module_name in alias.name:
                                blocking_imports.append(
                                    f"{py_file.relative_to(self.workspace_root)}: import {alias.name}"
                                )
                    
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and module_name in node.module:
                            imported_names = ', '.join(alias.name for alias in node.names)
                            blocking_imports.append(
                                f"{py_file.relative_to(self.workspace_root)}: from {node.module} import {imported_names}"
                            )
        
        except PermissionError as e:
            # If we can't access app/, be conservative
            error_msg = f"Permission denied accessing app/ directory: {e}"
            logger.error(error_msg)
            blocking_imports.append("app/: Permission denied (requires manual review)")
        except OSError as e:
            # If we can't access app/, be conservative
            error_msg = f"Error accessing app/ directory: {e}"
            logger.error(error_msg)
            blocking_imports.append("app/: Access error (requires manual review)")
        
        # Check config references and documentation links
        blocking_configs = self.check_config_references(file_path)
        blocking_docs = self.check_documentation_links(file_path)
        
        # File is safe to remove only if there are no blocking dependencies
        is_safe = (
            len(blocking_imports) == 0 and
            len(blocking_configs) == 0 and
            len(blocking_docs) == 0
        )
        
        return SafetyReport(
            file_path=file_path,
            is_safe_to_remove=is_safe,
            blocking_imports=blocking_imports,
            blocking_configs=blocking_configs,
            blocking_docs=blocking_docs
        )
    
    def check_config_references(self, file_path: Path) -> List[str]:
        """Find references in configuration files.
        
        Scans pyproject.toml, alembic.ini, and docker-compose.yml for any
        references to the given file path.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            List of configuration file references (e.g., "pyproject.toml:15: reference")
            
        Error Handling:
            - Config file malformed: log error, skip that config, continue
            - Config file doesn't exist: log warning, continue
            - File cannot be read: skip file, continue
        """
        blocking_configs = []
        
        # Configuration files to check
        config_files = [
            self.workspace_root / 'pyproject.toml',
            self.workspace_root / 'alembic.ini',
            self.workspace_root / 'docker-compose.yml',
            self.workspace_root / 'docker-compose.yaml',
        ]
        
        # Get the filename to search for
        filename = file_path.name
        
        # Also check for the relative path from workspace root
        try:
            relative_path = file_path.relative_to(self.workspace_root)
            relative_path_str = str(relative_path).replace('\\', '/')
        except ValueError:
            # File is not relative to workspace root
            relative_path_str = filename
        
        for config_file in config_files:
            # Handle config file doesn't exist: log warning, continue
            if not config_file.exists():
                logger.debug(f"Config file doesn't exist, skipping: {config_file}")
                continue
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except FileNotFoundError:
                # File was deleted between exists check and open
                logger.warning(f"Config file not found: {config_file}")
                continue
            except PermissionError:
                # Handle file cannot be read: skip file, continue
                logger.warning(f"Permission denied reading config file: {config_file}")
                continue
            except UnicodeDecodeError as e:
                # Handle config file malformed: log error, skip that config, continue
                error_msg = f"Config file has encoding issues: {config_file} - {e}"
                logger.error(error_msg)
                continue
            except OSError as e:
                # Handle file cannot be read: skip file, continue
                logger.warning(f"Error reading config file {config_file}: {e}")
                continue
            
            # Search for references to the file
            for line_num, line in enumerate(lines, start=1):
                # Check if the filename or relative path appears in this line
                if filename in line or relative_path_str in line:
                    blocking_configs.append(
                        f"{config_file.name}:{line_num}: {line.strip()}"
                    )
        
        return blocking_configs
    
    def check_documentation_links(self, file_path: Path) -> List[str]:
        """Find references in documentation.
        
        Parses markdown files in wiki/ for relative links to the given file.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            List of documentation references (e.g., "wiki/guide.md:42: [link](../file.py)")
            
        Error Handling:
            - File cannot be read: skip file, continue
        """
        blocking_docs = []
        
        # Only check if wiki/ directory exists
        if not self.wiki_dir.exists():
            return blocking_docs
        
        # Get the filename to search for
        filename = file_path.name
        
        # Also check for the relative path from workspace root
        try:
            relative_path = file_path.relative_to(self.workspace_root)
            relative_path_str = str(relative_path).replace('\\', '/')
        except ValueError:
            # File is not relative to workspace root
            relative_path_str = filename
        
        # Regex pattern to match markdown links: [text](url)
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')
        
        try:
            for md_file in self.wiki_dir.rglob('*.md'):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                except FileNotFoundError:
                    # Skip files that don't exist
                    logger.debug(f"File not found, skipping: {md_file}")
                    continue
                except PermissionError:
                    # Skip files we can't read
                    logger.debug(f"Permission denied, skipping: {md_file}")
                    continue
                except UnicodeDecodeError:
                    # Skip binary files
                    logger.debug(f"Binary file or encoding issue, skipping: {md_file}")
                    continue
                except OSError as e:
                    # Skip files with other read errors
                    logger.debug(f"Error reading file {md_file}: {e}")
                    continue
                
                # Search for links to the file
                for line_num, line in enumerate(lines, start=1):
                    # Find all markdown links in this line
                    matches = link_pattern.findall(line)
                    
                    for link_text, link_url in matches:
                        # Check if the link references our file
                        if filename in link_url or relative_path_str in link_url:
                            blocking_docs.append(
                                f"{md_file.relative_to(self.workspace_root)}:{line_num}: [{link_text}]({link_url})"
                            )
        
        except PermissionError as e:
            # If we can't access wiki/, return empty list
            logger.warning(f"Permission denied accessing wiki/ directory: {e}")
        except OSError as e:
            # If we can't access wiki/, return empty list
            logger.warning(f"Error accessing wiki/ directory: {e}")
        
        return blocking_docs
    
    def verify_test_imports(self, moved_tests: List[Path]) -> ImportVerification:
        """Verify test imports resolve after moving to tests/.
        
        Checks if all import statements in moved test files can still be resolved.
        Detects relative imports that need updating (e.g., from test_helper import fixture).
        
        Args:
            moved_tests: List of test file paths in their new location (tests/ directory)
            
        Returns:
            ImportVerification with broken imports list
            
        Error Handling:
            - File cannot be read: skip file, continue
            - AST parsing fails: log error, record as broken import
        """
        broken_imports: List[Tuple[Path, str]] = []
        
        for test_file in moved_tests:
            if not test_file.exists():
                # File doesn't exist, skip it
                logger.debug(f"Test file doesn't exist, skipping: {test_file}")
                continue
            
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            except FileNotFoundError:
                # File was deleted between exists check and open
                logger.debug(f"Test file not found, skipping: {test_file}")
                continue
            except PermissionError:
                # Skip files we can't read
                logger.warning(f"Permission denied reading test file: {test_file}")
                continue
            except UnicodeDecodeError:
                # Skip binary files
                logger.warning(f"Binary file or encoding issue: {test_file}")
                continue
            except OSError as e:
                # Skip files with other read errors
                logger.warning(f"Error reading test file {test_file}: {e}")
                continue
            
            # Parse the file with AST
            try:
                tree = ast.parse(content, filename=str(test_file))
            except SyntaxError as e:
                # Handle AST parsing fails: log error, record as broken import
                error_msg = f"Syntax error parsing test file: {test_file} - {e}"
                logger.error(error_msg)
                broken_imports.append((test_file, f"AST parsing failed: {str(e)}"))
                continue
            except ValueError as e:
                # Handle AST parsing fails: log error, record as broken import
                error_msg = f"AST parsing failed for test file: {test_file} - {e}"
                logger.error(error_msg)
                broken_imports.append((test_file, f"AST parsing failed: {str(e)}"))
                continue
            except Exception as e:
                # Handle unexpected parsing errors
                error_msg = f"Unexpected error parsing test file: {test_file} - {e}"
                logger.error(error_msg)
                broken_imports.append((test_file, f"Unexpected parsing error: {str(e)}"))
                continue
            
            # Check all import statements
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Check if this import can be resolved
                        if not self._can_resolve_import(alias.name, test_file):
                            # Handle module not found: record as broken import for reporting
                            broken_imports.append((test_file, f"import {alias.name}"))
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        # Check if this import can be resolved
                        if not self._can_resolve_import(node.module, test_file, is_from_import=True):
                            # Handle module not found: record as broken import for reporting
                            imported_names = ', '.join(alias.name for alias in node.names)
                            broken_imports.append((test_file, f"from {node.module} import {imported_names}"))
        
        return ImportVerification(
            all_imports_valid=(len(broken_imports) == 0),
            broken_imports=broken_imports
        )
    
    def _can_resolve_import(self, module_name: str, test_file: Path, is_from_import: bool = False) -> bool:
        """Check if an import can be resolved.
        
        Args:
            module_name: The module name to import (e.g., 'app.models', 'test_helper')
            test_file: The test file attempting the import
            is_from_import: Whether this is a 'from X import Y' statement
            
        Returns:
            True if the import can be resolved, False otherwise
        """
        # Split module name into parts
        parts = module_name.split('.')
        
        # Check if it's a standard library module
        if parts[0] in sys.stdlib_module_names:
            return True
        
        # Check if it's a relative import from the same directory
        # For example: from test_helper import fixture
        if len(parts) == 1:
            # Check if the module exists in the same directory as the test file
            same_dir_module = test_file.parent / f"{parts[0]}.py"
            if same_dir_module.exists():
                return True
        
        # Check if it's an absolute import from workspace root
        # For example: from app.models import User
        module_path = self.workspace_root / parts[0]
        
        # Check if it's a directory with __init__.py (package)
        if module_path.is_dir():
            init_file = module_path / '__init__.py'
            if init_file.exists():
                # Check nested modules
                current_path = module_path
                for part in parts[1:]:
                    current_path = current_path / part
                    if current_path.is_dir():
                        init_file = current_path / '__init__.py'
                        if not init_file.exists():
                            return False
                    elif not (current_path.with_suffix('.py')).exists():
                        return False
                return True
        
        # Check if it's a single module file
        module_file = self.workspace_root / f"{parts[0]}.py"
        if module_file.exists():
            return True
        
        # Check if it's a third-party package (we assume these are installed)
        # Common third-party packages used in tests
        common_packages = {
            'pytest', 'unittest', 'mock', 'hypothesis', 'faker',
            'requests', 'flask', 'fastapi', 'sqlalchemy', 'pydantic',
            'numpy', 'pandas', 'django', 'celery', 'redis'
        }
        if parts[0] in common_packages:
            return True
        
        # If we can't resolve it, it's likely broken
        return False
    
    def verify_pytest_discovery(self) -> DiscoveryReport:
        """Verify pytest can discover all tests in tests/.
        
        Runs pytest --collect-only programmatically to check if all test files
        in the tests/ directory can be discovered. This ensures that moved test
        files are still accessible to pytest after the move operation.
        
        Returns:
            DiscoveryReport with discovery results
        """
        import subprocess
        
        tests_dir = self.workspace_root / 'tests'
        
        # If tests/ directory doesn't exist, return successful report with no tests
        if not tests_dir.exists():
            return DiscoveryReport(
                discovery_successful=True,
                discovered_tests=[],
                errors=[],
                total_collected=0
            )
        
        try:
            # Run pytest --collect-only to discover tests without running them
            # Use -q for quiet output to reduce noise
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', '--collect-only', '-q', str(tests_dir)],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            discovered_tests = []
            errors = []
            total_collected = 0
            
            # Parse the output to extract discovered tests
            output_lines = result.stdout.split('\n')
            
            for line in output_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Pytest outputs test items in the format:
                # <Module test_file.py>
                # <Function test_something>
                # <Class TestSomething>
                if line.startswith('<') and line.endswith('>'):
                    discovered_tests.append(line)
                    total_collected += 1
                
                # Look for the summary line: "X tests collected" or "X test collected"
                elif 'collected' in line.lower():
                    # Extract the number of tests collected
                    import re
                    match = re.search(r'(\d+)\s+tests?\s+collected', line.lower())
                    if match:
                        total_collected = int(match.group(1))
            
            # Check stderr for errors
            if result.stderr:
                stderr_lines = result.stderr.split('\n')
                for line in stderr_lines:
                    line = line.strip()
                    if line and not line.startswith('='):
                        errors.append(line)
            
            # Discovery is successful if pytest exited with code 0 or 5
            # Code 0: tests collected successfully
            # Code 5: no tests collected (not an error)
            discovery_successful = result.returncode in (0, 5)
            
            # If pytest failed, add the return code to errors
            if not discovery_successful:
                errors.append(f"pytest exited with code {result.returncode}")
            
            return DiscoveryReport(
                discovery_successful=discovery_successful,
                discovered_tests=discovered_tests,
                errors=errors,
                total_collected=total_collected
            )
        
        except subprocess.TimeoutExpired:
            return DiscoveryReport(
                discovery_successful=False,
                discovered_tests=[],
                errors=["pytest --collect-only timed out after 30 seconds"],
                total_collected=0
            )
        
        except FileNotFoundError:
            return DiscoveryReport(
                discovery_successful=False,
                discovered_tests=[],
                errors=["pytest is not installed or not found in PATH"],
                total_collected=0
            )
        
        except Exception as e:
            return DiscoveryReport(
                discovery_successful=False,
                discovered_tests=[],
                errors=[f"Unexpected error during pytest discovery: {str(e)}"],
                total_collected=0
            )
