"""
CE Chat Runtime Rollout Configuration.

Defines the rollout checklist, pilot user group criteria, success metrics,
rollback procedure, and monitoring dashboard requirements for the controlled
rollout of the Context Engineering chat runtime (Phase 6.4).

All thresholds and criteria are codified here so they can be referenced
programmatically by monitoring, rollback automation, and the dashboard.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 6.4.1 – Rollout Checklist
# ---------------------------------------------------------------------------

class ChecklistItemStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class ChecklistItem:
    """A single item on the rollout checklist."""
    id: str
    description: str
    phase: str
    status: ChecklistItemStatus = ChecklistItemStatus.NOT_STARTED
    owner: str = ""
    notes: str = ""


def get_rollout_checklist() -> List[ChecklistItem]:
    """Return the full rollout checklist for CE chat runtime migration."""
    return [
        # Pre-rollout
        ChecklistItem(
            id="PRE-01",
            description="All Phase 1-5 exit criteria validated",
            phase="pre-rollout",
        ),
        ChecklistItem(
            id="PRE-02",
            description="Feature flags configured (USE_CE_CHAT_RUNTIME, LEGACY_CHAT_ENABLED)",
            phase="pre-rollout",
        ),
        ChecklistItem(
            id="PRE-03",
            description="Side-by-side comparison completed with acceptable results",
            phase="pre-rollout",
        ),
        ChecklistItem(
            id="PRE-04",
            description="Telemetry pipeline verified (invocations.jsonl rotation, archival)",
            phase="pre-rollout",
        ),
        ChecklistItem(
            id="PRE-05",
            description="Rollback procedure documented and tested",
            phase="pre-rollout",
        ),
        ChecklistItem(
            id="PRE-06",
            description="Monitoring dashboard deployed and receiving data",
            phase="pre-rollout",
        ),
        ChecklistItem(
            id="PRE-07",
            description="Pilot user group identified and notified",
            phase="pre-rollout",
        ),
        # Pilot rollout
        ChecklistItem(
            id="PILOT-01",
            description="Enable USE_CE_CHAT_RUNTIME=true for pilot group",
            phase="pilot",
        ),
        ChecklistItem(
            id="PILOT-02",
            description="Monitor p95 latency for 48 hours (target < 3s simple, < 5s multi-tool)",
            phase="pilot",
        ),
        ChecklistItem(
            id="PILOT-03",
            description="Monitor error rate for 48 hours (target < 1%)",
            phase="pilot",
        ),
        ChecklistItem(
            id="PILOT-04",
            description="Collect pilot user feedback (minimum 5 responses)",
            phase="pilot",
        ),
        ChecklistItem(
            id="PILOT-05",
            description="Verify no session data corruption or leakage",
            phase="pilot",
        ),
        # General availability
        ChecklistItem(
            id="GA-01",
            description="Pilot success metrics met for 2 consecutive weeks",
            phase="general-availability",
        ),
        ChecklistItem(
            id="GA-02",
            description="Enable USE_CE_CHAT_RUNTIME=true for all users",
            phase="general-availability",
        ),
        ChecklistItem(
            id="GA-03",
            description="Monitor full-fleet metrics for 1 week",
            phase="general-availability",
        ),
        ChecklistItem(
            id="GA-04",
            description="Disable LEGACY_CHAT_ENABLED after 2 weeks stable",
            phase="general-availability",
        ),
        ChecklistItem(
            id="GA-05",
            description="Remove legacy code paths per deprecation plan",
            phase="general-availability",
        ),
    ]


# ---------------------------------------------------------------------------
# 6.4.2 – Pilot User Group
# ---------------------------------------------------------------------------

@dataclass
class PilotGroupConfig:
    """Configuration for the pilot user group.

    The pilot group is selected to cover diverse usage patterns while
    keeping the blast radius small during initial rollout.
    """

    # Selection criteria
    min_sessions_last_30_days: int = 5
    """Users must have at least this many chat sessions in the last 30 days."""

    max_pilot_users: int = 20
    """Maximum number of users in the pilot group."""

    min_pilot_users: int = 5
    """Minimum viable pilot group size for meaningful metrics."""

    include_tool_heavy_users: bool = True
    """Include users who frequently trigger multi-tool queries."""

    include_simple_query_users: bool = True
    """Include users who primarily ask simple coaching questions."""

    pilot_duration_days: int = 14
    """Duration of the pilot phase before GA decision."""

    # Exclusion criteria
    exclude_new_users_days: int = 7
    """Exclude users who signed up fewer than this many days ago."""


def get_pilot_group_config() -> PilotGroupConfig:
    """Return the default pilot group configuration."""
    return PilotGroupConfig()


def build_pilot_user_query_filter(config: PilotGroupConfig) -> Dict:
    """Return a filter dict describing the SQL criteria for pilot user selection.

    This is a specification – the actual query is executed by the caller
    against the ChatSession / User tables.

    Returns:
        Dict with keys that map to query conditions.
    """
    return {
        "min_sessions_last_30_days": config.min_sessions_last_30_days,
        "exclude_new_users_days": config.exclude_new_users_days,
        "max_results": config.max_pilot_users,
        "order_by": "session_count_desc",
        "description": (
            f"Select up to {config.max_pilot_users} users with >= "
            f"{config.min_sessions_last_30_days} sessions in the last 30 days, "
            f"excluding users created within the last {config.exclude_new_users_days} days. "
            "Order by session count descending to prioritise active users."
        ),
    }


# ---------------------------------------------------------------------------
# 6.4.3 – Success Metrics
# ---------------------------------------------------------------------------

@dataclass
class SuccessMetrics:
    """Quantitative thresholds that must be met for the rollout to proceed.

    Each metric maps to a telemetry field in ``InvocationLog`` or can be
    derived from the ``invocations.jsonl`` records.
    """

    # Latency
    p95_latency_simple_ms: float = 3000.0
    """p95 latency for simple (no-tool) queries must be below this value."""

    p95_latency_multi_tool_ms: float = 5000.0
    """p95 latency for multi-tool queries must be below this value."""

    context_build_latency_ms: float = 500.0
    """Context building (retrieval + assembly) must complete within this time."""

    rag_retrieval_latency_ms: float = 200.0
    """RAG retrieval for up to 20 records must complete within this time."""

    # Reliability
    error_rate_threshold: float = 0.01
    """Maximum acceptable error rate (1%)."""

    fallback_rate_threshold: float = 0.10
    """Maximum acceptable fallback model usage rate (10%)."""

    tool_success_rate_min: float = 0.95
    """Minimum tool execution success rate (95%)."""

    # Quality
    token_budget_compliance: float = 1.0
    """100% of requests must stay within the 2400-token budget."""

    session_data_integrity: float = 1.0
    """No session data corruption or cross-session leakage (100%)."""

    # Comparison (CE vs legacy)
    max_latency_regression_pct: float = 10.0
    """CE latency must not exceed legacy by more than this percentage."""

    min_quality_parity: float = 0.95
    """CE response quality score must be >= this fraction of legacy score."""

    # Stability
    stability_window_days: int = 14
    """Metrics must hold for this many consecutive days before GA."""


def get_success_metrics() -> SuccessMetrics:
    """Return the default success metrics for CE chat rollout."""
    return SuccessMetrics()


def evaluate_metric(name: str, actual: float, metrics: Optional[SuccessMetrics] = None) -> bool:
    """Check whether a single metric meets its threshold.

    Args:
        name: Attribute name on ``SuccessMetrics`` (e.g. ``"error_rate_threshold"``).
        actual: The observed value.
        metrics: Metrics instance (uses defaults if *None*).

    Returns:
        *True* if the metric passes, *False* otherwise.
    """
    if metrics is None:
        metrics = get_success_metrics()

    threshold = getattr(metrics, name, None)
    if threshold is None:
        raise ValueError(f"Unknown metric: {name}")

    # For "min" metrics, actual must be >= threshold
    if name.startswith("min_") or name in (
        "tool_success_rate_min",
        "token_budget_compliance",
        "session_data_integrity",
        "min_quality_parity",
    ):
        return actual >= threshold

    # For "stability_window_days", actual must be >= threshold
    if name == "stability_window_days":
        return actual >= threshold

    # For everything else (latency, rates), actual must be <= threshold
    return actual <= threshold


# ---------------------------------------------------------------------------
# 6.4.4 – Rollback Procedure
# ---------------------------------------------------------------------------

class RollbackSeverity(str, Enum):
    """Severity levels that trigger different rollback responses."""
    CRITICAL = "critical"   # Immediate full rollback
    HIGH = "high"           # Rollback within 1 hour
    MEDIUM = "medium"       # Investigate, rollback if not resolved in 4 hours
    LOW = "low"             # Monitor, no automatic rollback


@dataclass
class RollbackTrigger:
    """A condition that triggers a rollback action."""
    id: str
    description: str
    severity: RollbackSeverity
    metric_name: str
    threshold_description: str


@dataclass
class RollbackStep:
    """A single step in the rollback procedure."""
    order: int
    action: str
    command: str = ""
    verification: str = ""


@dataclass
class RollbackProcedure:
    """Complete rollback procedure for CE chat runtime."""
    triggers: List[RollbackTrigger] = field(default_factory=list)
    steps: List[RollbackStep] = field(default_factory=list)


def get_rollback_procedure() -> RollbackProcedure:
    """Return the rollback procedure with triggers and steps."""
    triggers = [
        RollbackTrigger(
            id="RB-01",
            description="Error rate exceeds 5% over 15-minute window",
            severity=RollbackSeverity.CRITICAL,
            metric_name="error_rate_threshold",
            threshold_description="> 5% errors in 15 min",
        ),
        RollbackTrigger(
            id="RB-02",
            description="p95 latency exceeds 10s for simple queries",
            severity=RollbackSeverity.CRITICAL,
            metric_name="p95_latency_simple_ms",
            threshold_description="> 10000 ms p95",
        ),
        RollbackTrigger(
            id="RB-03",
            description="Session data corruption detected",
            severity=RollbackSeverity.CRITICAL,
            metric_name="session_data_integrity",
            threshold_description="Any corruption event",
        ),
        RollbackTrigger(
            id="RB-04",
            description="p95 latency exceeds 3s for simple queries (sustained 1 hour)",
            severity=RollbackSeverity.HIGH,
            metric_name="p95_latency_simple_ms",
            threshold_description="> 3000 ms p95 for 1 hour",
        ),
        RollbackTrigger(
            id="RB-05",
            description="Fallback rate exceeds 20% over 1-hour window",
            severity=RollbackSeverity.HIGH,
            metric_name="fallback_rate_threshold",
            threshold_description="> 20% fallback in 1 hour",
        ),
        RollbackTrigger(
            id="RB-06",
            description="Tool success rate drops below 80%",
            severity=RollbackSeverity.MEDIUM,
            metric_name="tool_success_rate_min",
            threshold_description="< 80% tool success",
        ),
        RollbackTrigger(
            id="RB-07",
            description="Token budget exceeded in > 5% of requests",
            severity=RollbackSeverity.LOW,
            metric_name="token_budget_compliance",
            threshold_description="< 95% compliance",
        ),
    ]

    steps = [
        RollbackStep(
            order=1,
            action="Set USE_CE_CHAT_RUNTIME=false in environment",
            command='Set environment variable: USE_CE_CHAT_RUNTIME=false',
            verification="Confirm setting reads false via /health or config endpoint",
        ),
        RollbackStep(
            order=2,
            action="Verify LEGACY_CHAT_ENABLED=true (should already be true during rollout)",
            command='Verify environment variable: LEGACY_CHAT_ENABLED=true',
            verification="Confirm legacy runtime is active in application logs",
        ),
        RollbackStep(
            order=3,
            action="Restart application to pick up config changes",
            command="Restart the application service",
            verification="Check startup logs for 'runtime=legacy' indicator",
        ),
        RollbackStep(
            order=4,
            action="Verify chat functionality on legacy runtime",
            command="Send test chat message and verify response",
            verification="Confirm response received with runtime=legacy in metadata",
        ),
        RollbackStep(
            order=5,
            action="Check telemetry for post-rollback error rate",
            command="Review invocations.jsonl for errors in last 5 minutes",
            verification="Error rate returns to baseline (< 1%)",
        ),
        RollbackStep(
            order=6,
            action="Notify team of rollback with incident details",
            command="Post incident summary to team channel",
            verification="Team acknowledges and begins root cause analysis",
        ),
    ]

    return RollbackProcedure(triggers=triggers, steps=steps)


# ---------------------------------------------------------------------------
# 6.4.5 – Monitoring Dashboard Requirements
# ---------------------------------------------------------------------------

class WidgetType(str, Enum):
    TIME_SERIES = "time_series"
    GAUGE = "gauge"
    TABLE = "table"
    COUNTER = "counter"
    HEATMAP = "heatmap"


@dataclass
class DashboardWidget:
    """Specification for a single monitoring dashboard widget."""
    id: str
    title: str
    widget_type: WidgetType
    data_source: str
    description: str
    refresh_interval_seconds: int = 30
    alert_threshold: Optional[str] = None


@dataclass
class DashboardSpec:
    """Full specification for the CE chat runtime monitoring dashboard."""
    name: str
    description: str
    widgets: List[DashboardWidget] = field(default_factory=list)


def get_monitoring_dashboard_spec() -> DashboardSpec:
    """Return the monitoring dashboard specification.

    All widgets source data from ``invocations.jsonl`` telemetry records
    (``InvocationLog`` fields) or derived aggregations.
    """
    widgets = [
        # Latency
        DashboardWidget(
            id="latency-p95",
            title="Chat p95 Latency (ms)",
            widget_type=WidgetType.TIME_SERIES,
            data_source="invocations.jsonl:total_latency_ms (p95, 5-min buckets)",
            description="p95 end-to-end latency over time, split by simple vs multi-tool queries.",
            alert_threshold="simple > 3000 ms, multi-tool > 5000 ms",
        ),
        DashboardWidget(
            id="latency-breakdown",
            title="Latency Breakdown",
            widget_type=WidgetType.TIME_SERIES,
            data_source="invocations.jsonl:retrieval_latency_ms, model_latency_ms",
            description="Stacked time series showing retrieval vs model latency contributions.",
        ),
        # Error rate
        DashboardWidget(
            id="error-rate",
            title="Error Rate (%)",
            widget_type=WidgetType.TIME_SERIES,
            data_source="invocations.jsonl:success_status (rolling 15-min window)",
            description="Percentage of failed invocations over time.",
            alert_threshold="> 1% sustained, > 5% critical",
        ),
        # Fallback usage
        DashboardWidget(
            id="fallback-rate",
            title="Fallback Model Usage (%)",
            widget_type=WidgetType.GAUGE,
            data_source="invocations.jsonl:fallback_used (rolling 1-hour window)",
            description="Percentage of requests served by fallback model.",
            alert_threshold="> 10% warning, > 20% critical",
        ),
        # Token usage
        DashboardWidget(
            id="token-usage",
            title="Token Usage Distribution",
            widget_type=WidgetType.HEATMAP,
            data_source="invocations.jsonl:context_token_count, response_token_count",
            description="Distribution of input/output token counts per request.",
        ),
        DashboardWidget(
            id="token-budget",
            title="Token Budget Compliance",
            widget_type=WidgetType.GAUGE,
            data_source="invocations.jsonl:context_token_count <= 2400",
            description="Percentage of requests within the 2400-token budget.",
            alert_threshold="< 100% warning",
        ),
        # Runtime comparison
        DashboardWidget(
            id="runtime-split",
            title="Active Runtime Distribution",
            widget_type=WidgetType.COUNTER,
            data_source="invocations.jsonl:operation_type (ce vs legacy count)",
            description="Count of requests handled by CE vs legacy runtime.",
        ),
        # Throughput
        DashboardWidget(
            id="request-throughput",
            title="Chat Requests / Minute",
            widget_type=WidgetType.TIME_SERIES,
            data_source="invocations.jsonl:timestamp (count per minute)",
            description="Request throughput over time.",
        ),
        # Tool execution
        DashboardWidget(
            id="tool-success-rate",
            title="Tool Execution Success Rate",
            widget_type=WidgetType.GAUGE,
            data_source="tool_invocations.jsonl:success (rolling 1-hour window)",
            description="Percentage of tool calls that completed successfully.",
            alert_threshold="< 95% warning, < 80% critical",
        ),
        # Recent errors table
        DashboardWidget(
            id="recent-errors",
            title="Recent Errors",
            widget_type=WidgetType.TABLE,
            data_source="invocations.jsonl:error_message WHERE success_status=false",
            description="Table of recent error messages with timestamp, athlete_id, and operation_type.",
            refresh_interval_seconds=15,
        ),
    ]

    return DashboardSpec(
        name="CE Chat Runtime Monitor",
        description=(
            "Real-time monitoring dashboard for the Context Engineering chat runtime rollout. "
            "Sources data from invocations.jsonl and tool_invocations.jsonl telemetry files."
        ),
        widgets=widgets,
    )
