"""Data models for workspace cleanup system."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple, Dict


@dataclass
class FileInventory:
    """Complete inventory of workspace files."""
    
    root_documentation: List[Path] = field(default_factory=list)
    root_tests_py: List[Path] = field(default_factory=list)
    root_tests_html: List[Path] = field(default_factory=list)
    root_tests_db: List[Path] = field(default_factory=list)
    specs_files: List[Path] = field(default_factory=list)
    protected_files: Set[Path] = field(default_factory=set)
    
    def total_files_to_process(self) -> int:
        """Returns count of all files requiring processing."""
        return (
            len(self.root_documentation)
            + len(self.root_tests_py)
            + len(self.root_tests_html)
            + len(self.root_tests_db)
            + len(self.specs_files)
        )


@dataclass
class ObsolescenceReport:
    """Report on whether a file is obsolete."""
    
    file_path: Path
    is_obsolete: bool
    reason: str
    confidence: float  # 0.0 to 1.0


@dataclass
class ContentEvaluation:
    """Evaluation of whether a file contains valuable content."""
    
    file_path: Path
    has_value: bool
    reason: str
    recommended_action: str  # "move_to_wiki", "remove"


@dataclass
class DuplicateGroup:
    """Group of test files with duplicate functionality."""
    
    files: List[Path] = field(default_factory=list)
    shared_test_functions: Set[str] = field(default_factory=set)
    shared_imports: Set[str] = field(default_factory=set)
    similarity_score: float = 0.0  # 0.0 to 1.0


@dataclass
class SafetyReport:
    """Report on whether a file is safe to remove."""
    
    file_path: Path
    is_safe_to_remove: bool
    blocking_imports: List[str] = field(default_factory=list)
    blocking_configs: List[str] = field(default_factory=list)
    blocking_docs: List[str] = field(default_factory=list)


@dataclass
class ImportVerification:
    """Verification of test imports after moving to tests/ directory."""
    
    all_imports_valid: bool
    broken_imports: List[Tuple[Path, str]] = field(default_factory=list)  # (file, import_statement)


@dataclass
class DiscoveryReport:
    """Report on pytest test discovery results."""
    
    discovery_successful: bool
    discovered_tests: List[str] = field(default_factory=list)  # List of discovered test items
    errors: List[str] = field(default_factory=list)  # List of discovery errors
    total_collected: int = 0  # Total number of tests collected


@dataclass
class MoveResult:
    """Result of a file move operation."""
    
    success: bool
    source: Path
    destination: Path
    error: Optional[str] = None


@dataclass
class RemovalResult:
    """Result of a file removal operation."""
    
    success: bool
    file_path: Path
    reason: str
    error: Optional[str] = None


@dataclass
class Operation:
    """Record of a file operation."""
    
    type: str  # "move", "remove", "preserve"
    file_path: Path
    destination: Optional[Path] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CleanupPlan:
    """Complete plan for workspace cleanup."""

    files_to_move_to_wiki: List[Tuple[Path, Path]] = field(default_factory=list)  # (source, dest)
    files_to_move_to_tests: List[Tuple[Path, Path]] = field(default_factory=list)
    files_to_remove: List[Tuple[Path, str]] = field(default_factory=list)  # (file, reason)
    files_to_preserve: List[Path] = field(default_factory=list)
    protected_files: Set[Path] = field(default_factory=set)  # Files that must not be modified
    workspace_root: Optional[Path] = None  # Root directory for validation

    def validate(self) -> List[str]:
        """Returns list of validation errors, empty if valid.

        Checks:
        - No file appears in multiple operation lists
        - All destination directories exist or can be created
        - No protected files are in operation lists

        Returns:
            List of validation error messages, empty if valid
        """
        errors = []

        # Collect all files in operations
        all_files: Set[Path] = set()

        # Check for duplicates in move to wiki
        wiki_sources = [src for src, _ in self.files_to_move_to_wiki]
        for src in wiki_sources:
            if src in all_files:
                errors.append(f"File {src} appears in multiple operations")
            all_files.add(src)

        # Check for duplicates in move to tests
        test_sources = [src for src, _ in self.files_to_move_to_tests]
        for src in test_sources:
            if src in all_files:
                errors.append(f"File {src} appears in multiple operations")
            all_files.add(src)

        # Check for duplicates in remove
        remove_files = [file for file, _ in self.files_to_remove]
        for src in remove_files:
            if src in all_files:
                errors.append(f"File {src} appears in multiple operations")
            all_files.add(src)

        # Check for duplicates in preserve
        for src in self.files_to_preserve:
            if src in all_files:
                errors.append(f"File {src} appears in multiple operations")
            all_files.add(src)

        # Check for protected files in operations
        for src in all_files:
            if src in self.protected_files:
                errors.append(f"Protected file {src} cannot be modified")

        # Check destination directories
        destination_dirs: Set[Path] = set()

        # Collect destination directories from move operations
        for _, dest in self.files_to_move_to_wiki:
            destination_dirs.add(dest.parent)

        for _, dest in self.files_to_move_to_tests:
            destination_dirs.add(dest.parent)

        # Validate each destination directory
        for dest_dir in destination_dirs:
            if dest_dir.exists():
                if not dest_dir.is_dir():
                    errors.append(f"Destination path {dest_dir} exists but is not a directory")
            else:
                # Check if we can create the directory (parent must exist and be writable)
                parent = dest_dir.parent
                if not parent.exists():
                    errors.append(f"Cannot create destination directory {dest_dir}: parent {parent} does not exist")
                elif not parent.is_dir():
                    errors.append(f"Cannot create destination directory {dest_dir}: parent {parent} is not a directory")

        return errors



@dataclass
class VerificationResults:
    """Results of post-cleanup verification."""
    
    all_imports_valid: bool = True
    broken_imports: List[Tuple[Path, str]] = field(default_factory=list)
    all_links_valid: bool = True
    broken_links: List[Tuple[Path, str]] = field(default_factory=list)
    pytest_discovery_success: bool = True
    pytest_errors: List[str] = field(default_factory=list)


@dataclass
class CleanupReport:
    """Final report of all cleanup operations."""
    
    moved_to_wiki: List[Operation] = field(default_factory=list)
    moved_to_tests: List[Operation] = field(default_factory=list)
    removed_files: List[Operation] = field(default_factory=list)
    preserved_files: List[Path] = field(default_factory=list)
    verification_results: Optional[VerificationResults] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_markdown(self) -> str:
        """Generates markdown report."""
        lines = [
            "# Workspace Cleanup Report",
            "",
            f"Generated: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        
        # Moved to wiki section
        lines.extend([
            "## Files Moved to Wiki",
            "",
        ])
        if self.moved_to_wiki:
            for op in self.moved_to_wiki:
                # Use forward slashes for consistency across platforms
                src = str(op.file_path).replace("\\", "/")
                dst = str(op.destination).replace("\\", "/")
                lines.append(f"- `{src}` → `{dst}`")
        else:
            lines.append("No files moved to wiki.")
        lines.append("")
        
        # Moved to tests section
        lines.extend([
            "## Files Moved to Tests",
            "",
        ])
        if self.moved_to_tests:
            for op in self.moved_to_tests:
                # Use forward slashes for consistency across platforms
                src = str(op.file_path).replace("\\", "/")
                dst = str(op.destination).replace("\\", "/")
                lines.append(f"- `{src}` → `{dst}`")
        else:
            lines.append("No files moved to tests.")
        lines.append("")
        
        # Removed files section
        lines.extend([
            "## Files Removed",
            "",
        ])
        if self.removed_files:
            for op in self.removed_files:
                # Use forward slashes for consistency across platforms
                src = str(op.file_path).replace("\\", "/")
                lines.append(f"- `{src}` - {op.reason}")
        else:
            lines.append("No files removed.")
        lines.append("")
        
        # Preserved files section
        lines.extend([
            "## Files Preserved",
            "",
        ])
        if self.preserved_files:
            for file in self.preserved_files:
                # Use forward slashes for consistency across platforms
                src = str(file).replace("\\", "/")
                lines.append(f"- `{src}`")
        else:
            lines.append("No files explicitly preserved.")
        lines.append("")
        
        # Verification results section
        if self.verification_results:
            lines.extend([
                "## Verification Results",
                "",
            ])
            
            vr = self.verification_results
            
            # Import verification
            if vr.all_imports_valid:
                lines.append("✓ All imports valid")
            else:
                lines.append("✗ Broken imports detected:")
                for file, import_stmt in vr.broken_imports:
                    lines.append(f"  - `{file}`: {import_stmt}")
            lines.append("")
            
            # Link verification
            if vr.all_links_valid:
                lines.append("✓ All documentation links valid")
            else:
                lines.append("✗ Broken links detected:")
                for file, link in vr.broken_links:
                    lines.append(f"  - `{file}`: {link}")
            lines.append("")
            
            # Pytest discovery
            if vr.pytest_discovery_success:
                lines.append("✓ Pytest discovery successful")
            else:
                lines.append("✗ Pytest discovery issues:")
                for error in vr.pytest_errors:
                    lines.append(f"  - {error}")
            lines.append("")
        
        return "\n".join(lines)
