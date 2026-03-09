"""File mover component for workspace cleanup system."""

import errno
import logging
import shutil
import stat
from pathlib import Path
from typing import Optional, List

from .models import MoveResult, RemovalResult, CleanupReport

logger = logging.getLogger(__name__)


class FileMover:
    """Executes file operations safely with atomic moves."""
    
    def __init__(self):
        """Initialize the file mover with error tracking."""
        self.errors: List[str] = []
        self.manual_intervention_files: List[tuple[Path, str]] = []
    
    def move_file(self, source: Path, destination: Path) -> MoveResult:
        """
        Moves a file atomically with verification.
        
        Args:
            source: Source file path
            destination: Destination file path
            
        Returns:
            MoveResult with success status and any error message
            
        Requirements:
            - 1.6: Verify each file exists in destination after move
            - 1.7: Verify each file no longer exists at source after move
            - 3.5: Maintain file naming conventions
            - 3.6: Verify each test file exists in destination after move
            - 7.7: Preserve file permissions
            
        Error Handling:
            - Source file doesn't exist: log error, skip file, continue
            - Destination file already exists: log error, skip file, continue
            - Destination directory doesn't exist: create directory, retry
            - Permission denied: log error, mark for manual intervention, continue
            - File locked: log error, mark for manual intervention, continue
        """
        # Handle source file doesn't exist
        if not source.exists():
            error_msg = f"Source file does not exist: {source}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        
        # Handle destination file already exists (avoid overwrites)
        if destination.exists():
            error_msg = f"Destination file already exists: {destination}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        
        # Get source file permissions before moving
        try:
            source_permissions = source.stat().st_mode
        except PermissionError as e:
            error_msg = f"Permission denied reading source file permissions: {source} - {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            self.manual_intervention_files.append((source, "Permission denied"))
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        except OSError as e:
            error_msg = f"Failed to read source file permissions: {source} - {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        
        # Handle destination directory doesn't exist: create directory, retry
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            error_msg = f"Permission denied creating destination directory: {destination.parent} - {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            self.manual_intervention_files.append((source, "Permission denied creating destination directory"))
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        except OSError as e:
            error_msg = f"Failed to create destination directory: {destination.parent} - {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        
        # Perform atomic move using shutil.move()
        try:
            shutil.move(str(source), str(destination))
        except PermissionError as e:
            error_msg = f"Permission denied moving file: {source} -> {destination} - {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            self.manual_intervention_files.append((source, "Permission denied"))
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        except OSError as e:
            # Check if it's a file locked error (errno 13 on Windows, errno 16 on Unix)
            if e.errno in (errno.EACCES, errno.EBUSY, errno.ETXTBSY):
                error_msg = f"File locked or in use: {source} - {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                self.manual_intervention_files.append((source, "File locked"))
                return MoveResult(
                    success=False,
                    source=source,
                    destination=destination,
                    error=error_msg
                )
            else:
                error_msg = f"Failed to move file: {source} -> {destination} - {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                return MoveResult(
                    success=False,
                    source=source,
                    destination=destination,
                    error=error_msg
                )
        except shutil.Error as e:
            error_msg = f"Failed to move file: {source} -> {destination} - {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        
        # Verify file exists at destination after move
        if not destination.exists():
            error_msg = f"File does not exist at destination after move: {destination}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        
        # Verify file no longer exists at source after move
        if source.exists():
            error_msg = f"File still exists at source after move: {source}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return MoveResult(
                success=False,
                source=source,
                destination=destination,
                error=error_msg
            )
        
        # Preserve file permissions
        try:
            destination.chmod(source_permissions)
        except PermissionError as e:
            # File was moved successfully, but permissions couldn't be set
            # This is a partial success - log warning but don't fail
            warning_msg = f"Warning: Permission denied setting file permissions: {destination} - {e}"
            logger.warning(warning_msg)
            return MoveResult(
                success=True,
                source=source,
                destination=destination,
                error=warning_msg
            )
        except OSError as e:
            # File was moved successfully, but permissions couldn't be set
            # This is a partial success - log warning but don't fail
            warning_msg = f"Warning: Failed to preserve file permissions: {destination} - {e}"
            logger.warning(warning_msg)
            return MoveResult(
                success=True,
                source=source,
                destination=destination,
                error=warning_msg
            )
        
        # Verify permissions were preserved
        try:
            dest_permissions = destination.stat().st_mode
            if dest_permissions != source_permissions:
                warning_msg = f"Warning: File permissions differ (source: {oct(source_permissions)}, dest: {oct(dest_permissions)})"
                logger.warning(warning_msg)
                return MoveResult(
                    success=True,
                    source=source,
                    destination=destination,
                    error=warning_msg
                )
        except OSError as e:
            warning_msg = f"Warning: Failed to verify file permissions: {destination} - {e}"
            logger.warning(warning_msg)
            return MoveResult(
                success=True,
                source=source,
                destination=destination,
                error=warning_msg
            )
        
        return MoveResult(
            success=True,
            source=source,
            destination=destination,
            error=None
        )


    def remove_file(self, file_path: Path, reason: str) -> RemovalResult:
        """
        Removes a file safely with logging.

        Args:
            file_path: Path to the file to remove
            reason: Reason for removal (for logging)

        Returns:
            RemovalResult with success status and any error message

        Requirements:
            - 2.5: Remove files that don't contain valuable content
            - 2.6: Remove files that don't contain valuable content
            - 2.7: Remove empty directories after file removal
            - 5.5: Only remove files verified safe by DependencyChecker
            - 5.6: Create removal log documenting each deleted file
            
        Error Handling:
            - File doesn't exist: log warning, skip file, continue
            - Permission denied: log error, mark for manual intervention, continue
            - File locked: log error, mark for manual intervention, continue
        """
        # Log file path and reason before removal
        logger.info(f"Removing file: {file_path} - Reason: {reason}")

        # Handle file doesn't exist
        if not file_path.exists():
            warning_msg = f"File does not exist (already removed): {file_path}"
            logger.warning(warning_msg)
            # This is not a critical error - file is already gone
            return RemovalResult(
                success=True,
                file_path=file_path,
                reason=reason,
                error=warning_msg
            )

        # Verify it's a file, not a directory
        if not file_path.is_file():
            error_msg = f"Path is not a file: {file_path}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return RemovalResult(
                success=False,
                file_path=file_path,
                reason=reason,
                error=error_msg
            )

        # Store parent directory for empty directory cleanup
        parent_dir = file_path.parent

        # Remove the file using Path.unlink()
        try:
            file_path.unlink()
        except PermissionError as e:
            error_msg = f"Permission denied removing file: {file_path} - {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            self.manual_intervention_files.append((file_path, "Permission denied"))
            return RemovalResult(
                success=False,
                file_path=file_path,
                reason=reason,
                error=error_msg
            )
        except OSError as e:
            # Check if it's a file locked error
            if e.errno in (errno.EACCES, errno.EBUSY, errno.ETXTBSY):
                error_msg = f"File locked or in use: {file_path} - {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                self.manual_intervention_files.append((file_path, "File locked"))
                return RemovalResult(
                    success=False,
                    file_path=file_path,
                    reason=reason,
                    error=error_msg
                )
            else:
                error_msg = f"Failed to remove file: {file_path} - {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                return RemovalResult(
                    success=False,
                    file_path=file_path,
                    reason=reason,
                    error=error_msg
                )

        # Verify file no longer exists
        if file_path.exists():
            error_msg = f"File still exists after removal: {file_path}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return RemovalResult(
                success=False,
                file_path=file_path,
                reason=reason,
                error=error_msg
            )

        # Remove empty directories after file removal
        try:
            # Only remove if directory is empty and not a protected directory
            if parent_dir.exists() and not any(parent_dir.iterdir()):
                # Don't remove root-level directories or protected directories
                protected_dirs = {'app', 'alembic', 'public', 'scripts', '.kiro', 'wiki', 'tests'}
                if parent_dir.name not in protected_dirs and parent_dir != Path('.'):
                    logger.info(f"Removing empty directory: {parent_dir}")
                    parent_dir.rmdir()
        except PermissionError as e:
            # Directory removal failure is not critical - log warning but don't fail
            warning_msg = f"Permission denied removing empty directory {parent_dir}: {e}"
            logger.warning(warning_msg)
        except OSError as e:
            # Directory removal failure is not critical - log warning but don't fail
            warning_msg = f"Failed to remove empty directory {parent_dir}: {e}"
            logger.warning(warning_msg)

        return RemovalResult(
            success=True,
            file_path=file_path,
            reason=reason,
            error=None
        )

    def get_errors(self) -> List[str]:
        """
        Get all collected errors.
        
        Returns:
            List of error messages
        """
        return self.errors.copy()
    
    def get_manual_intervention_files(self) -> List[tuple[Path, str]]:
        """
        Get all files that require manual intervention.
        
        Returns:
            List of (file_path, reason) tuples
        """
        return self.manual_intervention_files.copy()
    
    def clear_errors(self):
        """Clear all collected errors and manual intervention files."""
        self.errors.clear()
        self.manual_intervention_files.clear()


    def generate_cleanup_report(self, report: CleanupReport, output_path: Optional[Path] = None) -> Path:
        """
        Generates a comprehensive markdown report of all cleanup operations.

        Args:
            report: CleanupReport object containing all operation details
            output_path: Optional custom output path. Defaults to wiki/WORKSPACE_CLEANUP_REPORT.md

        Returns:
            Path to the generated report file

        Requirements:
            - 8.1: Generate report listing all files moved to wiki
            - 8.2: Generate report listing all files moved to tests
            - 8.3: Generate report listing all files removed as obsolete
            - 8.4: Generate report listing all files preserved
            - 8.5: Include original and new file paths for moved files
            - 8.6: Include justifications for removed files
            - 8.7: Save report to wiki/WORKSPACE_CLEANUP_REPORT.md
        """
        # Use default path if not provided
        if output_path is None:
            output_path = Path("wiki") / "WORKSPACE_CLEANUP_REPORT.md"

        # Ensure the output directory exists
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create output directory {output_path.parent}: {e}")
            raise

        # Generate markdown content using CleanupReport's to_markdown() method
        markdown_content = report.to_markdown()

        # Write the report to file
        try:
            output_path.write_text(markdown_content, encoding='utf-8')
            logger.info(f"Cleanup report saved to: {output_path}")
        except OSError as e:
            logger.error(f"Failed to write cleanup report to {output_path}: {e}")
            raise

        return output_path
