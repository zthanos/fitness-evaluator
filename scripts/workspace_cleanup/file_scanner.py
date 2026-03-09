"""File scanner for workspace cleanup system."""

from pathlib import Path
from typing import Dict, List, Set

from .models import FileInventory


class FileScanner:
    """Discovers and categorizes files in the workspace."""
    
    def __init__(self, workspace_root: Path):
        """Initialize the file scanner.
        
        Args:
            workspace_root: Path to the workspace root directory
        """
        self.workspace_root = workspace_root
        # Hidden directories to filter out (but not .kiro which is protected)
        self._hidden_dirs = {'.git', '.venv', '__pycache__', 'node_modules', '.pytest_cache'}
    
    def scan_root_documentation(self) -> List[Path]:
        """Find markdown files in workspace root.
        
        Returns:
            List of Path objects for markdown files in the workspace root
        """
        markdown_files = []
        
        # Only scan the root directory, not subdirectories
        for item in self.workspace_root.iterdir():
            if item.is_file() and item.suffix == '.md':
                markdown_files.append(item)
        
        return markdown_files
    
    def scan_root_tests(self) -> Dict[str, List[Path]]:
        """Find test files in workspace root.
        
        Returns:
            Dictionary with keys 'py', 'html', 'db' containing lists of test files
        """
        test_files = {
            'py': [],
            'html': [],
            'db': []
        }
        
        # Only scan the root directory, not subdirectories
        for item in self.workspace_root.iterdir():
            if item.is_file() and item.name.startswith('test_'):
                if item.suffix == '.py':
                    test_files['py'].append(item)
                elif item.suffix == '.html':
                    test_files['html'].append(item)
                elif item.suffix == '.db':
                    test_files['db'].append(item)
        
        return test_files
    
    def scan_specs_folder(self) -> List[Path]:
        """Find files in specs/ directory.
        
        Returns:
            List of Path objects for files in the specs/ directory
        """
        specs_dir = self.workspace_root / 'specs'
        
        if not specs_dir.exists() or not specs_dir.is_dir():
            return []
        
        files = []
        for item in specs_dir.rglob('*'):
            # Skip specific hidden directories
            if any(part in self._hidden_dirs for part in item.parts):
                continue
            
            if item.is_file():
                files.append(item)
        
        return files
    
    def get_protected_directories(self) -> Set[Path]:
        """Get directories that must not be modified.
        
        Returns:
            Set of Path objects for protected directories
        """
        protected = {
            self.workspace_root / 'app',
            self.workspace_root / 'alembic',
            self.workspace_root / 'public',
            self.workspace_root / 'scripts',
            self.workspace_root / '.kiro' / 'specs'
        }
        
        return protected
    
    def scan_workspace(self) -> FileInventory:
        """Perform a complete scan of the workspace.
        
        Returns:
            FileInventory object containing all categorized files
        """
        inventory = FileInventory()
        
        # Scan root documentation
        inventory.root_documentation = self.scan_root_documentation()
        
        # Scan root tests
        test_files = self.scan_root_tests()
        inventory.root_tests_py = test_files['py']
        inventory.root_tests_html = test_files['html']
        inventory.root_tests_db = test_files['db']
        
        # Scan specs folder
        inventory.specs_files = self.scan_specs_folder()
        
        # Get protected directories
        protected_dirs = self.get_protected_directories()
        
        # Collect all files in protected directories
        for protected_dir in protected_dirs:
            if protected_dir.exists() and protected_dir.is_dir():
                for item in protected_dir.rglob('*'):
                    # Skip specific hidden directories
                    if any(part in self._hidden_dirs for part in item.parts):
                        continue
                    
                    if item.is_file():
                        inventory.protected_files.add(item)
        
        return inventory
