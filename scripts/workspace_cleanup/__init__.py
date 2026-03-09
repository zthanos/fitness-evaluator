"""Workspace cleanup and reorganization system.

This package provides tools for consolidating test files, moving documentation,
evaluating legacy content, and safely removing obsolete code.
"""

from .models import (
    FileInventory,
    CleanupPlan,
    CleanupReport,
    ObsolescenceReport,
    ContentEvaluation,
    SafetyReport,
    MoveResult,
    RemovalResult,
    Operation,
)

__all__ = [
    "FileInventory",
    "CleanupPlan",
    "CleanupReport",
    "ObsolescenceReport",
    "ContentEvaluation",
    "SafetyReport",
    "MoveResult",
    "RemovalResult",
    "Operation",
]
