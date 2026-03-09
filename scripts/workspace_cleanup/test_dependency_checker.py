"""Unit tests for DependencyChecker class."""

import tempfile
from pathlib import Path

import pytest

from .dependency_checker import DependencyChecker
from .models import SafetyReport


class TestDependencyChecker:
    """Test suite for DependencyChecker class."""
    
    def test_check_import_safety_no_imports(self):
        """Test that a file with no imports is safe to remove."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create app/ directory with a file that doesn't import anything
            app_dir = workspace / 'app'
            app_dir.mkdir()
            
            app_file = app_dir / 'main.py'
            app_file.write_text('print("Hello, world!")')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check import safety
            checker = DependencyChecker(workspace)
            report = checker.check_import_safety(test_file)
            
            assert isinstance(report, SafetyReport)
            assert report.file_path == test_file
            assert report.is_safe_to_remove is True
            assert len(report.blocking_imports) == 0
    
    def test_check_import_safety_with_import(self):
        """Test that a file imported by app/ is not safe to remove."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create app/ directory with a file that imports test_foo
            app_dir = workspace / 'app'
            app_dir.mkdir()
            
            app_file = app_dir / 'main.py'
            app_file.write_text('import test_foo\n\ntest_foo.run()')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def run(): pass')
            
            # Check import safety
            checker = DependencyChecker(workspace)
            report = checker.check_import_safety(test_file)
            
            assert isinstance(report, SafetyReport)
            assert report.file_path == test_file
            assert report.is_safe_to_remove is False
            assert len(report.blocking_imports) > 0
            assert 'import test_foo' in report.blocking_imports[0]
    
    def test_check_import_safety_with_from_import(self):
        """Test that a file imported with 'from' is not safe to remove."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create app/ directory with a file that imports from test_foo
            app_dir = workspace / 'app'
            app_dir.mkdir()
            
            app_file = app_dir / 'main.py'
            app_file.write_text('from test_foo import run\n\nrun()')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def run(): pass')
            
            # Check import safety
            checker = DependencyChecker(workspace)
            report = checker.check_import_safety(test_file)
            
            assert isinstance(report, SafetyReport)
            assert report.file_path == test_file
            assert report.is_safe_to_remove is False
            assert len(report.blocking_imports) > 0
            assert 'from test_foo import' in report.blocking_imports[0]
    
    def test_check_import_safety_no_app_directory(self):
        """Test that files are safe when app/ directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create a test file to check (no app/ directory)
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check import safety
            checker = DependencyChecker(workspace)
            report = checker.check_import_safety(test_file)
            
            assert isinstance(report, SafetyReport)
            assert report.file_path == test_file
            assert report.is_safe_to_remove is True
            assert len(report.blocking_imports) == 0
    
    def test_check_config_references_no_references(self):
        """Test that a file with no config references returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create a config file that doesn't reference test_foo
            config_file = workspace / 'pyproject.toml'
            config_file.write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check config references
            checker = DependencyChecker(workspace)
            references = checker.check_config_references(test_file)
            
            assert isinstance(references, list)
            assert len(references) == 0
    
    def test_check_config_references_with_reference(self):
        """Test that a file referenced in config is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create a config file that references test_foo.py
            config_file = workspace / 'pyproject.toml'
            config_file.write_text('[tool.pytest.ini_options]\naddopts = "--ignore=test_foo.py"')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check config references
            checker = DependencyChecker(workspace)
            references = checker.check_config_references(test_file)
            
            assert isinstance(references, list)
            assert len(references) > 0
            assert 'pyproject.toml' in references[0]
            assert 'test_foo.py' in references[0]
    
    def test_check_config_references_multiple_files(self):
        """Test checking references across multiple config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create multiple config files
            pyproject = workspace / 'pyproject.toml'
            pyproject.write_text('[tool.pytest.ini_options]\naddopts = "--ignore=test_foo.py"')
            
            alembic = workspace / 'alembic.ini'
            alembic.write_text('[alembic]\nscript_location = test_foo.py')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check config references
            checker = DependencyChecker(workspace)
            references = checker.check_config_references(test_file)
            
            assert isinstance(references, list)
            assert len(references) == 2
            assert any('pyproject.toml' in ref for ref in references)
            assert any('alembic.ini' in ref for ref in references)
    
    def test_check_documentation_links_no_links(self):
        """Test that a file with no doc links returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create wiki/ directory with a file that doesn't link to test_foo
            wiki_dir = workspace / 'wiki'
            wiki_dir.mkdir()
            
            doc_file = wiki_dir / 'guide.md'
            doc_file.write_text('# Guide\n\nThis is a guide.')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check documentation links
            checker = DependencyChecker(workspace)
            links = checker.check_documentation_links(test_file)
            
            assert isinstance(links, list)
            assert len(links) == 0
    
    def test_check_documentation_links_with_link(self):
        """Test that a file linked in documentation is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create wiki/ directory with a file that links to test_foo.py
            wiki_dir = workspace / 'wiki'
            wiki_dir.mkdir()
            
            doc_file = wiki_dir / 'guide.md'
            doc_file.write_text('# Guide\n\nSee [test file](../test_foo.py) for examples.')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check documentation links
            checker = DependencyChecker(workspace)
            links = checker.check_documentation_links(test_file)
            
            assert isinstance(links, list)
            assert len(links) > 0
            assert 'guide.md' in links[0]
            assert 'test_foo.py' in links[0]
    
    def test_check_documentation_links_no_wiki_directory(self):
        """Test that files are safe when wiki/ directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create a test file to check (no wiki/ directory)
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check documentation links
            checker = DependencyChecker(workspace)
            links = checker.check_documentation_links(test_file)
            
            assert isinstance(links, list)
            assert len(links) == 0
    
    def test_check_import_safety_integration(self):
        """Test full integration of import, config, and doc checking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create app/ directory
            app_dir = workspace / 'app'
            app_dir.mkdir()
            app_file = app_dir / 'main.py'
            app_file.write_text('print("No imports")')
            
            # Create wiki/ directory
            wiki_dir = workspace / 'wiki'
            wiki_dir.mkdir()
            doc_file = wiki_dir / 'guide.md'
            doc_file.write_text('# Guide\n\nSee [test](../test_foo.py).')
            
            # Create config file
            config_file = workspace / 'pyproject.toml'
            config_file.write_text('[tool.pytest.ini_options]\naddopts = "--ignore=test_foo.py"')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check import safety (should detect config and doc references)
            checker = DependencyChecker(workspace)
            report = checker.check_import_safety(test_file)
            
            assert isinstance(report, SafetyReport)
            assert report.file_path == test_file
            assert report.is_safe_to_remove is False
            assert len(report.blocking_imports) == 0
            assert len(report.blocking_configs) > 0
            assert len(report.blocking_docs) > 0
    
    def test_check_import_safety_with_syntax_error(self):
        """Test that files with syntax errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create app/ directory with a file that has syntax errors
            app_dir = workspace / 'app'
            app_dir.mkdir()
            
            app_file = app_dir / 'main.py'
            app_file.write_text('import test_foo\n\ndef broken(:\n    pass')
            
            # Create a test file to check
            test_file = workspace / 'test_foo.py'
            test_file.write_text('def test_foo(): pass')
            
            # Check import safety (should handle syntax error gracefully)
            checker = DependencyChecker(workspace)
            report = checker.check_import_safety(test_file)
            
            assert isinstance(report, SafetyReport)
            assert report.file_path == test_file
            # With enhanced error handling, syntax errors require manual review (not safe to remove)
            assert report.is_safe_to_remove is False
            assert len(report.blocking_imports) > 0
            assert "AST parsing failed" in report.blocking_imports[0]
    
    def test_verify_test_imports_all_valid(self):
        """Test that valid imports are correctly verified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create app/ directory with a module
            app_dir = workspace / 'app'
            app_dir.mkdir()
            (app_dir / '__init__.py').write_text('')
            
            models_file = app_dir / 'models.py'
            models_file.write_text('class User: pass')
            
            # Create tests/ directory with a test file
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            test_file = tests_dir / 'test_user.py'
            test_file.write_text('from app.models import User\n\ndef test_user(): pass')
            
            # Verify test imports
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([test_file])
            
            assert verification.all_imports_valid is True
            assert len(verification.broken_imports) == 0
    
    def test_verify_test_imports_broken_import(self):
        """Test that broken imports are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create tests/ directory with a test file that imports non-existent module
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            test_file = tests_dir / 'test_user.py'
            test_file.write_text('from nonexistent_module import Something\n\ndef test_user(): pass')
            
            # Verify test imports
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([test_file])
            
            assert verification.all_imports_valid is False
            assert len(verification.broken_imports) > 0
            assert test_file in [file for file, _ in verification.broken_imports]
            assert 'nonexistent_module' in verification.broken_imports[0][1]
    
    def test_verify_test_imports_relative_import_same_dir(self):
        """Test that relative imports from same directory are resolved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create tests/ directory with helper and test file
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            helper_file = tests_dir / 'test_helper.py'
            helper_file.write_text('def fixture(): pass')
            
            test_file = tests_dir / 'test_user.py'
            test_file.write_text('from test_helper import fixture\n\ndef test_user(): pass')
            
            # Verify test imports
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([test_file])
            
            assert verification.all_imports_valid is True
            assert len(verification.broken_imports) == 0
    
    def test_verify_test_imports_broken_relative_import(self):
        """Test that broken relative imports are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create tests/ directory with test file that imports non-existent helper
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            test_file = tests_dir / 'test_user.py'
            test_file.write_text('from test_helper import fixture\n\ndef test_user(): pass')
            
            # Verify test imports (test_helper.py doesn't exist)
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([test_file])
            
            assert verification.all_imports_valid is False
            assert len(verification.broken_imports) > 0
            assert 'test_helper' in verification.broken_imports[0][1]
    
    def test_verify_test_imports_standard_library(self):
        """Test that standard library imports are always valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create tests/ directory with test file using standard library
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            test_file = tests_dir / 'test_user.py'
            test_file.write_text('import os\nimport sys\nfrom pathlib import Path\n\ndef test_user(): pass')
            
            # Verify test imports
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([test_file])
            
            assert verification.all_imports_valid is True
            assert len(verification.broken_imports) == 0
    
    def test_verify_test_imports_third_party_packages(self):
        """Test that common third-party packages are assumed valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create tests/ directory with test file using third-party packages
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            test_file = tests_dir / 'test_user.py'
            test_file.write_text('import pytest\nfrom hypothesis import given\n\ndef test_user(): pass')
            
            # Verify test imports
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([test_file])
            
            assert verification.all_imports_valid is True
            assert len(verification.broken_imports) == 0
    
    def test_verify_test_imports_multiple_files(self):
        """Test verifying imports across multiple test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create app/ directory
            app_dir = workspace / 'app'
            app_dir.mkdir()
            (app_dir / '__init__.py').write_text('')
            (app_dir / 'models.py').write_text('class User: pass')
            
            # Create tests/ directory with multiple test files
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            test_file1 = tests_dir / 'test_user.py'
            test_file1.write_text('from app.models import User\n\ndef test_user(): pass')
            
            test_file2 = tests_dir / 'test_broken.py'
            test_file2.write_text('from nonexistent import Something\n\ndef test_broken(): pass')
            
            # Verify test imports
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([test_file1, test_file2])
            
            assert verification.all_imports_valid is False
            assert len(verification.broken_imports) == 1
            assert test_file2 in [file for file, _ in verification.broken_imports]
    
    def test_verify_test_imports_nonexistent_file(self):
        """Test that nonexistent files are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create tests/ directory
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            # Reference a file that doesn't exist
            nonexistent_file = tests_dir / 'test_nonexistent.py'
            
            # Verify test imports
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([nonexistent_file])
            
            assert verification.all_imports_valid is True
            assert len(verification.broken_imports) == 0
    
    def test_verify_test_imports_syntax_error(self):
        """Test that files with syntax errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create tests/ directory with a file that has syntax errors
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            test_file = tests_dir / 'test_broken.py'
            test_file.write_text('import pytest\n\ndef broken(:\n    pass')
            
            # Verify test imports (should handle syntax error gracefully)
            checker = DependencyChecker(workspace)
            verification = checker.verify_test_imports([test_file])
            
            # With enhanced error handling, syntax errors are recorded as broken imports
            assert verification.all_imports_valid is False
            assert len(verification.broken_imports) == 1
            assert "AST parsing failed" in verification.broken_imports[0][1]

    def test_verify_pytest_discovery_no_tests_dir(self):
        """Test that discovery succeeds when tests/ directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Don't create tests/ directory
            checker = DependencyChecker(workspace)
            report = checker.verify_pytest_discovery()
            
            assert report.discovery_successful is True
            assert len(report.discovered_tests) == 0
            assert len(report.errors) == 0
            assert report.total_collected == 0
    
    def test_verify_pytest_discovery_with_tests(self):
        """Test that pytest can discover tests in tests/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create tests/ directory with test files
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            test_file1 = tests_dir / 'test_example.py'
            test_file1.write_text('''
def test_one():
    assert True

def test_two():
    assert True
''')
            
            test_file2 = tests_dir / 'test_another.py'
            test_file2.write_text('''
def test_three():
    assert True
''')
            
            # Verify pytest discovery
            checker = DependencyChecker(workspace)
            report = checker.verify_pytest_discovery()
            
            # Discovery should succeed
            assert report.discovery_successful is True
            # Should have collected some tests
            assert report.total_collected >= 3
            # Should have no errors
            assert len(report.errors) == 0
    
    def test_verify_pytest_discovery_empty_tests_dir(self):
        """Test that discovery succeeds with empty tests/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create empty tests/ directory
            tests_dir = workspace / 'tests'
            tests_dir.mkdir()
            
            # Verify pytest discovery
            checker = DependencyChecker(workspace)
            report = checker.verify_pytest_discovery()
            
            # Discovery should succeed (no tests is not an error)
            assert report.discovery_successful is True
            assert report.total_collected == 0
