"""Unit tests for FileScanner class."""

import tempfile
from pathlib import Path
import pytest

from .file_scanner import FileScanner
from .models import FileInventory


class TestFileScanner:
    """Test suite for FileScanner class."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create some markdown files in root
            (workspace / "README.md").touch()
            (workspace / "CHANGELOG.md").touch()
            
            # Create some test files in root
            (workspace / "test_example.py").touch()
            (workspace / "test_another.html").touch()
            (workspace / "test_data.db").touch()
            
            # Create specs folder with files
            specs_dir = workspace / "specs"
            specs_dir.mkdir()
            (specs_dir / "plan.md").touch()
            (specs_dir / "tasks.md").touch()
            
            # Create protected directories
            (workspace / "app").mkdir()
            (workspace / "app" / "main.py").touch()
            (workspace / "alembic").mkdir()
            (workspace / "alembic" / "env.py").touch()
            (workspace / "public").mkdir()
            (workspace / "public" / "index.html").touch()
            (workspace / "scripts").mkdir()
            (workspace / "scripts" / "deploy.sh").touch()
            kiro_specs = workspace / ".kiro" / "specs"
            kiro_specs.mkdir(parents=True)
            (kiro_specs / "feature.md").touch()
            
            # Create hidden directories that should be filtered
            (workspace / ".git").mkdir()
            (workspace / ".git" / "config").touch()
            (workspace / ".venv").mkdir()
            (workspace / ".venv" / "lib").mkdir()
            
            yield workspace
    
    def test_scan_root_documentation(self, temp_workspace):
        """Test scanning for markdown files in workspace root."""
        scanner = FileScanner(temp_workspace)
        docs = scanner.scan_root_documentation()
        
        # Should find 2 markdown files
        assert len(docs) == 2
        
        # Check that the files are correct
        doc_names = {doc.name for doc in docs}
        assert "README.md" in doc_names
        assert "CHANGELOG.md" in doc_names
    
    def test_scan_root_tests(self, temp_workspace):
        """Test scanning for test files in workspace root."""
        scanner = FileScanner(temp_workspace)
        tests = scanner.scan_root_tests()
        
        # Should have all three types
        assert 'py' in tests
        assert 'html' in tests
        assert 'db' in tests
        
        # Check counts
        assert len(tests['py']) == 1
        assert len(tests['html']) == 1
        assert len(tests['db']) == 1
        
        # Check file names
        assert tests['py'][0].name == "test_example.py"
        assert tests['html'][0].name == "test_another.html"
        assert tests['db'][0].name == "test_data.db"
    
    def test_scan_specs_folder(self, temp_workspace):
        """Test scanning for files in specs/ directory."""
        scanner = FileScanner(temp_workspace)
        specs = scanner.scan_specs_folder()
        
        # Should find 2 files in specs
        assert len(specs) == 2
        
        # Check file names
        spec_names = {spec.name for spec in specs}
        assert "plan.md" in spec_names
        assert "tasks.md" in spec_names
    
    def test_scan_specs_folder_missing(self, temp_workspace):
        """Test scanning when specs/ folder doesn't exist."""
        # Remove specs folder
        import shutil
        shutil.rmtree(temp_workspace / "specs")
        
        scanner = FileScanner(temp_workspace)
        specs = scanner.scan_specs_folder()
        
        # Should return empty list
        assert len(specs) == 0
    
    def test_get_protected_directories(self, temp_workspace):
        """Test getting protected directories."""
        scanner = FileScanner(temp_workspace)
        protected = scanner.get_protected_directories()
        
        # Should have 5 protected directories
        assert len(protected) == 5
        
        # Check that all expected directories are present
        expected_dirs = {
            temp_workspace / "app",
            temp_workspace / "alembic",
            temp_workspace / "public",
            temp_workspace / "scripts",
            temp_workspace / ".kiro" / "specs"
        }
        assert protected == expected_dirs
    
    def test_scan_workspace_complete(self, temp_workspace):
        """Test complete workspace scan."""
        scanner = FileScanner(temp_workspace)
        inventory = scanner.scan_workspace()
        
        # Check that inventory is a FileInventory object
        assert isinstance(inventory, FileInventory)
        
        # Check documentation files
        assert len(inventory.root_documentation) == 2
        
        # Check test files
        assert len(inventory.root_tests_py) == 1
        assert len(inventory.root_tests_html) == 1
        assert len(inventory.root_tests_db) == 1
        
        # Check specs files
        assert len(inventory.specs_files) == 2
        
        # Check protected files (should include files from all protected directories)
        assert len(inventory.protected_files) > 0
        
        # Verify some protected files are present
        protected_file_names = {f.name for f in inventory.protected_files}
        assert "main.py" in protected_file_names
        assert "env.py" in protected_file_names
        assert "index.html" in protected_file_names
        assert "deploy.sh" in protected_file_names
        assert "feature.md" in protected_file_names
    
    def test_total_files_to_process(self, temp_workspace):
        """Test counting total files to process."""
        scanner = FileScanner(temp_workspace)
        inventory = scanner.scan_workspace()
        
        # Should be 2 docs + 3 tests + 2 specs = 7 files
        assert inventory.total_files_to_process() == 7
    
    def test_hidden_directories_filtered(self, temp_workspace):
        """Test that hidden directories are filtered out."""
        scanner = FileScanner(temp_workspace)
        inventory = scanner.scan_workspace()
        
        # Check that no files from .git or .venv are in protected files
        protected_paths = {str(f) for f in inventory.protected_files}
        
        # Should not contain any .git or .venv files
        assert not any('.git' in path for path in protected_paths)
        assert not any('.venv' in path for path in protected_paths)
    
    def test_scan_root_only_not_subdirectories(self, temp_workspace):
        """Test that root scans don't include subdirectories."""
        # Create a subdirectory with markdown and test files
        subdir = temp_workspace / "subdir"
        subdir.mkdir()
        (subdir / "README.md").touch()
        (subdir / "test_sub.py").touch()
        
        scanner = FileScanner(temp_workspace)
        
        # Scan documentation
        docs = scanner.scan_root_documentation()
        doc_names = {doc.name for doc in docs}
        
        # Should not include subdirectory markdown
        assert "README.md" in doc_names  # Root README
        assert len([d for d in docs if d.parent == subdir]) == 0
        
        # Scan tests
        tests = scanner.scan_root_tests()
        
        # Should not include subdirectory test
        assert len([t for t in tests['py'] if t.parent == subdir]) == 0
