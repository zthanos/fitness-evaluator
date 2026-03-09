#!/usr/bin/env python3
"""CLI script to run workspace cleanup."""

import argparse
import logging
import sys
from pathlib import Path

from .cleanup_orchestrator import CleanupOrchestrator


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the cleanup script.
    
    Args:
        verbose: If True, set log level to DEBUG, otherwise INFO
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("workspace_cleanup.log")
        ]
    )


def main() -> int:
    """Main entry point for the cleanup script.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Clean up and reorganize workspace files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run cleanup in current directory
  python run_cleanup.py
  
  # Dry run to see what would be done
  python run_cleanup.py --dry-run
  
  # Run with verbose logging
  python run_cleanup.py --verbose
  
  # Specify custom workspace path
  python run_cleanup.py --workspace /path/to/workspace
        """
    )
    
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd().parent.parent,  # Default to repo root (two levels up from scripts/workspace_cleanup)
        help="Path to workspace root directory (default: repository root)"
    )
    
    parser.add_argument(
        "--wiki",
        type=Path,
        default=None,
        help="Path to wiki directory (default: <workspace>/wiki)"
    )
    
    parser.add_argument(
        "--tests",
        type=Path,
        default=None,
        help="Path to tests directory (default: <workspace>/tests)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and plan without executing file operations"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Resolve paths
    workspace_root = args.workspace.resolve()
    wiki_dir = args.wiki.resolve() if args.wiki else workspace_root / "wiki"
    tests_dir = args.tests.resolve() if args.tests else workspace_root / "tests"
    
    # Validate workspace exists
    if not workspace_root.exists():
        logger.error(f"Workspace directory does not exist: {workspace_root}")
        return 1
    
    if not workspace_root.is_dir():
        logger.error(f"Workspace path is not a directory: {workspace_root}")
        return 1
    
    logger.info(f"Workspace root: {workspace_root}")
    logger.info(f"Wiki directory: {wiki_dir}")
    logger.info(f"Tests directory: {tests_dir}")
    
    if args.dry_run:
        logger.info("Running in DRY RUN mode - no files will be modified")
    
    try:
        # Create orchestrator and run cleanup
        orchestrator = CleanupOrchestrator(workspace_root, wiki_dir, tests_dir)
        report = orchestrator.run_cleanup(dry_run=args.dry_run)
        
        # Print summary
        print("\n" + "=" * 80)
        print("CLEANUP SUMMARY")
        print("=" * 80)
        print(f"Files moved to wiki: {len(report.moved_to_wiki)}")
        print(f"Files moved to tests: {len(report.moved_to_tests)}")
        print(f"Files removed: {len(report.removed_files)}")
        print(f"Files preserved: {len(report.preserved_files)}")
        
        if report.verification_results:
            print("\nVERIFICATION RESULTS:")
            vr = report.verification_results
            print(f"  Imports valid: {'✓' if vr.all_imports_valid else '✗'}")
            print(f"  Links valid: {'✓' if vr.all_links_valid else '✗'}")
            print(f"  Pytest discovery: {'✓' if vr.pytest_discovery_success else '✗'}")
            
            if not vr.all_imports_valid:
                print(f"\n  WARNING: {len(vr.broken_imports)} broken imports detected")
            if not vr.all_links_valid:
                print(f"  WARNING: {len(vr.broken_links)} broken links detected")
            if not vr.pytest_discovery_success:
                print(f"  WARNING: {len(vr.pytest_errors)} pytest discovery errors")
        
        if not args.dry_run:
            print(f"\nDetailed report saved to: {wiki_dir / 'WORKSPACE_CLEANUP_REPORT.md'}")
        
        print("=" * 80)
        
        logger.info("Cleanup completed successfully")
        return 0
        
    except Exception as e:
        logger.exception(f"Cleanup failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
