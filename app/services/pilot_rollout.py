"""
Pilot Rollout Service for CE Chat Runtime (Phase 6.6).

Provides per-user CE runtime enablement, pilot-group telemetry monitoring,
user feedback collection, structured bug tracking, and quality iteration
support for the controlled rollout of the Context Engineering chat runtime.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 6.6.1 – Pilot User Feature Flag
# ---------------------------------------------------------------------------


class PilotUserRegistry:
    """Manages the set of users enrolled in the CE runtime pilot.

    Users can be specified via the ``PILOT_USER_IDS`` setting (comma-separated)
    or added/removed at runtime.  The ``is_pilot_user`` check is used by
    ``ChatMessageHandler`` to decide which runtime to route a request to.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._runtime_additions: Set[int] = set()
        self._runtime_removals: Set[int] = set()

    @property
    def pilot_enabled(self) -> bool:
        """Whether pilot-based routing is active."""
        return self._settings.PILOT_ROLLOUT_ENABLED

    def is_pilot_user(self, user_id: int) -> bool:
        """Check if *user_id* should use the CE runtime.

        Resolution order:
        1. If pilot rollout is disabled → False
        2. If user was removed at runtime → False
        3. If user was added at runtime → True
        4. If user is in PILOT_USER_IDS config → True
        5. Otherwise → False
        """
        if not self.pilot_enabled:
            return False
        if user_id in self._runtime_removals:
            return False
        if user_id in self._runtime_additions:
            return True
        return user_id in self._settings.pilot_user_ids_set

    def add_pilot_user(self, user_id: int) -> None:
        """Add a user to the pilot group at runtime."""
        self._runtime_additions.add(user_id)
        self._runtime_removals.discard(user_id)
        logger.info("Added user %d to CE pilot group", user_id)

    def remove_pilot_user(self, user_id: int) -> None:
        """Remove a user from the pilot group at runtime."""
        self._runtime_removals.add(user_id)
        self._runtime_additions.discard(user_id)
        logger.info("Removed user %d from CE pilot group", user_id)

    def get_pilot_user_ids(self) -> Set[int]:
        """Return the effective set of pilot user IDs."""
        base = self._settings.pilot_user_ids_set
        return (base | self._runtime_additions) - self._runtime_removals

    def should_use_ce_runtime(self, user_id: int) -> bool:
        """Determine if a request from *user_id* should use the CE runtime.

        This combines the global ``USE_CE_CHAT_RUNTIME`` flag with
        pilot-specific routing:
        - If USE_CE_CHAT_RUNTIME is True globally → always CE
        - If pilot rollout is enabled and user is a pilot → CE
        - Otherwise → legacy
        """
        if self._settings.USE_CE_CHAT_RUNTIME:
            return True
        return self.is_pilot_user(user_id)


# ---------------------------------------------------------------------------
# 6.6.2 – Pilot Telemetry Monitoring
# ---------------------------------------------------------------------------


@dataclass
class PilotTelemetrySnapshot:
    """Aggregated telemetry metrics for the pilot group."""
    window_start: str
    window_end: str
    total_requests: int = 0
    pilot_requests: int = 0
    legacy_requests: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_count: int = 0
    error_rate: float = 0.0
    fallback_count: int = 0
    fallback_rate: float = 0.0
    avg_context_tokens: float = 0.0
    avg_response_tokens: float = 0.0


class PilotTelemetryMonitor:
    """Monitors telemetry specifically for the pilot user group.

    Reads from the invocations.jsonl telemetry file and filters/aggregates
    metrics for pilot users, enabling targeted monitoring during rollout.
    """

    def __init__(
        self,
        pilot_registry: PilotUserRegistry,
        telemetry_path: str = "app/ai/telemetry/invocations.jsonl",
    ):
        self._registry = pilot_registry
        self._telemetry_path = Path(telemetry_path)
        self._events: List[Dict[str, Any]] = []

    def record_event(self, event: Dict[str, Any]) -> None:
        """Record a telemetry event tagged with pilot status."""
        user_id = event.get("athlete_id", 0)
        event["is_pilot"] = self._registry.is_pilot_user(user_id)
        event["pilot_group"] = "pilot" if event["is_pilot"] else "control"
        self._events.append(event)

    def get_pilot_snapshot(
        self, window_minutes: int = 60
    ) -> PilotTelemetrySnapshot:
        """Aggregate pilot-group metrics over the given time window."""
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        now = datetime.utcnow()

        pilot_events = []
        for evt in self._events:
            ts = evt.get("timestamp", "")
            try:
                evt_time = datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                continue
            if evt_time >= cutoff and evt.get("is_pilot"):
                pilot_events.append(evt)

        total = len(self._events)
        pilot_count = len(pilot_events)
        legacy_count = total - pilot_count

        latencies = [e.get("total_latency_ms") or e.get("latency_ms", 0) for e in pilot_events]
        errors = [e for e in pilot_events if not e.get("success_status", True)]
        fallbacks = [e for e in pilot_events if e.get("fallback_used")]

        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
        ctx_tokens = [e.get("context_token_count", 0) for e in pilot_events]
        resp_tokens = [e.get("response_token_count", 0) for e in pilot_events]

        return PilotTelemetrySnapshot(
            window_start=cutoff.isoformat(),
            window_end=now.isoformat(),
            total_requests=total,
            pilot_requests=pilot_count,
            legacy_requests=legacy_count,
            avg_latency_ms=avg_lat,
            p95_latency_ms=p95_lat,
            error_count=len(errors),
            error_rate=len(errors) / pilot_count if pilot_count else 0.0,
            fallback_count=len(fallbacks),
            fallback_rate=len(fallbacks) / pilot_count if pilot_count else 0.0,
            avg_context_tokens=sum(ctx_tokens) / len(ctx_tokens) if ctx_tokens else 0.0,
            avg_response_tokens=sum(resp_tokens) / len(resp_tokens) if resp_tokens else 0.0,
        )

    def check_alerts(self, snapshot: Optional[PilotTelemetrySnapshot] = None) -> List[str]:
        """Return a list of alert messages if any thresholds are breached."""
        if snapshot is None:
            snapshot = self.get_pilot_snapshot()

        alerts: List[str] = []
        if snapshot.p95_latency_ms > 3000:
            alerts.append(
                f"ALERT: Pilot p95 latency {snapshot.p95_latency_ms:.0f}ms exceeds 3000ms target"
            )
        if snapshot.error_rate > 0.01:
            alerts.append(
                f"ALERT: Pilot error rate {snapshot.error_rate:.2%} exceeds 1% threshold"
            )
        if snapshot.fallback_rate > 0.10:
            alerts.append(
                f"ALERT: Pilot fallback rate {snapshot.fallback_rate:.2%} exceeds 10% threshold"
            )
        return alerts


# ---------------------------------------------------------------------------
# 6.6.3 – User Feedback Collection
# ---------------------------------------------------------------------------


class FeedbackRating(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class PilotFeedback:
    """A single feedback entry from a pilot user."""
    user_id: int
    session_id: int
    rating: str
    comment: str = ""
    timestamp: str = ""
    runtime: str = "ce"
    category: str = "general"


class FeedbackCollector:
    """Collects and stores feedback from pilot users.

    Feedback is stored in-memory and can be persisted to a JSONL file
    for analysis.
    """

    def __init__(self, storage_path: str = "app/ai/telemetry/pilot_feedback.jsonl"):
        self._storage_path = Path(storage_path)
        self._feedback: List[PilotFeedback] = []

    def submit_feedback(
        self,
        user_id: int,
        session_id: int,
        rating: str,
        comment: str = "",
        category: str = "general",
    ) -> PilotFeedback:
        """Submit feedback from a pilot user."""
        entry = PilotFeedback(
            user_id=user_id,
            session_id=session_id,
            rating=rating,
            comment=comment,
            timestamp=datetime.utcnow().isoformat(),
            runtime="ce",
            category=category,
        )
        self._feedback.append(entry)
        self._persist(entry)
        logger.info(
            "Pilot feedback received: user=%d rating=%s category=%s",
            user_id, rating, category,
        )
        return entry

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Return an aggregated summary of collected feedback."""
        total = len(self._feedback)
        if total == 0:
            return {"total": 0, "ratings": {}, "categories": {}}

        ratings: Dict[str, int] = {}
        categories: Dict[str, int] = {}
        for fb in self._feedback:
            ratings[fb.rating] = ratings.get(fb.rating, 0) + 1
            categories[fb.category] = categories.get(fb.category, 0) + 1

        return {
            "total": total,
            "ratings": ratings,
            "categories": categories,
            "satisfaction_rate": ratings.get("positive", 0) / total,
        }

    def get_all_feedback(self) -> List[PilotFeedback]:
        """Return all collected feedback entries."""
        return list(self._feedback)

    def _persist(self, entry: PilotFeedback) -> None:
        """Append a feedback entry to the JSONL storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "a", encoding="utf-8") as f:
            json.dump(asdict(entry), f, ensure_ascii=False)
            f.write("\n")


# ---------------------------------------------------------------------------
# 6.6.4 – Bug Identification and Tracking
# ---------------------------------------------------------------------------


class BugSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    FIXED = "fixed"
    WONT_FIX = "wont_fix"


@dataclass
class PilotBugReport:
    """A structured bug report from the pilot rollout."""
    id: str
    title: str
    severity: str
    status: str = "open"
    user_id: int = 0
    session_id: int = 0
    description: str = ""
    error_type: str = ""
    error_message: str = ""
    stack_trace: str = ""
    runtime: str = "ce"
    timestamp: str = ""
    resolution: str = ""


class BugTracker:
    """Tracks bugs identified during the pilot rollout.

    Provides structured logging, error categorization, and automatic
    bug detection from telemetry errors.
    """

    def __init__(self, storage_path: str = "app/ai/telemetry/pilot_bugs.jsonl"):
        self._storage_path = Path(storage_path)
        self._bugs: List[PilotBugReport] = []
        self._next_id = 1

    def report_bug(
        self,
        title: str,
        severity: str,
        user_id: int = 0,
        session_id: int = 0,
        description: str = "",
        error_type: str = "",
        error_message: str = "",
        stack_trace: str = "",
    ) -> PilotBugReport:
        """File a new bug report."""
        bug = PilotBugReport(
            id=f"PILOT-BUG-{self._next_id:04d}",
            title=title,
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            description=description,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            timestamp=datetime.utcnow().isoformat(),
        )
        self._next_id += 1
        self._bugs.append(bug)
        self._persist(bug)
        logger.warning(
            "Pilot bug reported: %s [%s] %s", bug.id, severity, title,
        )
        return bug

    def report_from_error(
        self,
        error: Exception,
        user_id: int = 0,
        session_id: int = 0,
    ) -> PilotBugReport:
        """Automatically create a bug report from an exception."""
        import traceback

        return self.report_bug(
            title=f"Auto-detected: {type(error).__name__}",
            severity=BugSeverity.HIGH.value,
            user_id=user_id,
            session_id=session_id,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
        )

    def update_status(self, bug_id: str, status: str, resolution: str = "") -> Optional[PilotBugReport]:
        """Update the status of an existing bug."""
        for bug in self._bugs:
            if bug.id == bug_id:
                bug.status = status
                bug.resolution = resolution
                logger.info("Bug %s status updated to %s", bug_id, status)
                return bug
        return None

    def get_open_bugs(self) -> List[PilotBugReport]:
        """Return all bugs that are not yet fixed."""
        return [b for b in self._bugs if b.status in ("open", "investigating")]

    def get_bugs_by_severity(self, severity: str) -> List[PilotBugReport]:
        """Return bugs filtered by severity."""
        return [b for b in self._bugs if b.severity == severity]

    def get_bug_summary(self) -> Dict[str, Any]:
        """Return an aggregated summary of tracked bugs."""
        total = len(self._bugs)
        by_severity: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for bug in self._bugs:
            by_severity[bug.severity] = by_severity.get(bug.severity, 0) + 1
            by_status[bug.status] = by_status.get(bug.status, 0) + 1

        return {
            "total": total,
            "by_severity": by_severity,
            "by_status": by_status,
            "open_count": by_status.get("open", 0) + by_status.get("investigating", 0),
        }

    def _persist(self, bug: PilotBugReport) -> None:
        """Append a bug report to the JSONL storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "a", encoding="utf-8") as f:
            json.dump(asdict(bug), f, ensure_ascii=False)
            f.write("\n")


# ---------------------------------------------------------------------------
# 6.6.5 – Quality Iteration Support
# ---------------------------------------------------------------------------


@dataclass
class QualityThreshold:
    """A configurable quality threshold for pilot monitoring."""
    name: str
    target: float
    warning: float
    critical: float
    unit: str = ""
    description: str = ""


@dataclass
class QualityCheckResult:
    """Result of a single quality check."""
    name: str
    actual: float
    target: float
    passed: bool
    level: str = "ok"  # ok, warning, critical


class QualityGate:
    """Configurable quality gate for iterating on pilot issues.

    Defines thresholds that must be met before expanding the rollout.
    Supports automated checks against telemetry snapshots.
    """

    DEFAULT_THRESHOLDS = [
        QualityThreshold(
            name="p95_latency_ms",
            target=3000.0, warning=2500.0, critical=5000.0,
            unit="ms", description="p95 end-to-end latency for simple queries",
        ),
        QualityThreshold(
            name="error_rate",
            target=0.01, warning=0.005, critical=0.05,
            unit="%", description="Request error rate",
        ),
        QualityThreshold(
            name="fallback_rate",
            target=0.10, warning=0.05, critical=0.20,
            unit="%", description="Fallback model usage rate",
        ),
        QualityThreshold(
            name="satisfaction_rate",
            target=0.80, warning=0.70, critical=0.50,
            unit="%", description="Pilot user satisfaction rate from feedback",
        ),
        QualityThreshold(
            name="open_bug_count",
            target=0, warning=3, critical=10,
            unit="count", description="Number of open bugs",
        ),
    ]

    def __init__(self, thresholds: Optional[List[QualityThreshold]] = None):
        self._thresholds = thresholds or list(self.DEFAULT_THRESHOLDS)

    def run_checks(
        self,
        telemetry: PilotTelemetrySnapshot,
        feedback_summary: Dict[str, Any],
        bug_summary: Dict[str, Any],
    ) -> List[QualityCheckResult]:
        """Run all quality checks against current data."""
        values = {
            "p95_latency_ms": telemetry.p95_latency_ms,
            "error_rate": telemetry.error_rate,
            "fallback_rate": telemetry.fallback_rate,
            "satisfaction_rate": feedback_summary.get("satisfaction_rate", 1.0),
            "open_bug_count": float(bug_summary.get("open_count", 0)),
        }

        results: List[QualityCheckResult] = []
        for threshold in self._thresholds:
            actual = values.get(threshold.name, 0.0)
            result = self._evaluate(threshold, actual)
            results.append(result)
        return results

    def all_passed(self, results: List[QualityCheckResult]) -> bool:
        """Check if all quality gates passed (no critical failures)."""
        return all(r.level != "critical" for r in results)

    def ready_for_expansion(self, results: List[QualityCheckResult]) -> bool:
        """Check if quality is good enough to expand the rollout."""
        return all(r.passed for r in results)

    def _evaluate(self, threshold: QualityThreshold, actual: float) -> QualityCheckResult:
        """Evaluate a single metric against its threshold."""
        # For "rate" metrics where lower is better (error_rate, fallback_rate)
        if threshold.name in ("error_rate", "fallback_rate", "p95_latency_ms", "open_bug_count"):
            if actual > threshold.critical:
                level = "critical"
            elif actual > threshold.target:
                level = "warning"
            else:
                level = "ok"
            passed = actual <= threshold.target
        else:
            # For metrics where higher is better (satisfaction_rate)
            if actual < threshold.critical:
                level = "critical"
            elif actual < threshold.target:
                level = "warning"
            else:
                level = "ok"
            passed = actual >= threshold.target

        return QualityCheckResult(
            name=threshold.name,
            actual=actual,
            target=threshold.target,
            passed=passed,
            level=level,
        )
