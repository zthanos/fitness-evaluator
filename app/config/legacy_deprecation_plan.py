"""Legacy Chat Runtime Deprecation Plan.

Codifies the timeline, legacy code inventory, stability requirements,
rollback procedure, and removal checklist for decommissioning the legacy
chat runtime after the CE (Context Engineering) migration is complete.

Requirements: 6.4 (Legacy Path Deprecation)
Tasks: 6.7.1 – 6.7.5
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 6.7.1 – Timeline for Legacy Removal
# ---------------------------------------------------------------------------

class MilestoneStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class DeprecationMilestone:
    """A single milestone in the legacy deprecation timeline."""
    id: str
    phase: str
    description: str
    duration_days: int
    prerequisites: List[str] = field(default_factory=list)
    status: MilestoneStatus = MilestoneStatus.NOT_STARTED
    notes: str = ""


def get_deprecation_timeline() -> List[DeprecationMilestone]:
    """Return the phased timeline for legacy chat runtime removal.

    The timeline is anchored to the moment the CE runtime is enabled
    for all users (GA).  All durations are relative to that anchor.

    Total estimated duration: ~6 weeks from pilot start to legacy removal.
    """
    return [
        # Phase A – Pilot (already defined in rollout_config)
        DeprecationMilestone(
            id="DEP-01",
            phase="pilot",
            description="CE runtime enabled for pilot user group",
            duration_days=14,
            prerequisites=["All Phase 1-5 exit criteria validated"],
        ),
        # Phase B – General Availability
        DeprecationMilestone(
            id="DEP-02",
            phase="general-availability",
            description="CE runtime enabled for all users (USE_CE_CHAT_RUNTIME=true)",
            duration_days=0,
            prerequisites=[
                "DEP-01 completed",
                "Pilot success metrics met for 14 consecutive days",
            ],
        ),
        # Phase C – Stability observation
        DeprecationMilestone(
            id="DEP-03",
            phase="stability-observation",
            description=(
                "Monitor CE runtime under full traffic for 14 days. "
                "Legacy path remains available but unused."
            ),
            duration_days=14,
            prerequisites=["DEP-02 completed"],
        ),
        # Phase D – Soft deprecation
        DeprecationMilestone(
            id="DEP-04",
            phase="soft-deprecation",
            description=(
                "Set LEGACY_CHAT_ENABLED=false. Legacy code still present "
                "but unreachable. Run full regression suite."
            ),
            duration_days=3,
            prerequisites=[
                "DEP-03 completed",
                "Stability requirements met (see get_stability_requirements)",
            ],
        ),
        # Phase E – Code removal
        DeprecationMilestone(
            id="DEP-05",
            phase="code-removal",
            description=(
                "Remove all legacy code, feature flags, comparison mode, "
                "and pilot routing. Follow removal checklist."
            ),
            duration_days=5,
            prerequisites=["DEP-04 completed"],
        ),
        # Phase F – Post-removal validation
        DeprecationMilestone(
            id="DEP-06",
            phase="post-removal",
            description=(
                "Run full test suite, verify no regressions, update docs. "
                "Legacy removal is complete."
            ),
            duration_days=2,
            prerequisites=["DEP-05 completed"],
        ),
    ]


# ---------------------------------------------------------------------------
# 6.7.2 – Legacy Code Inventory
# ---------------------------------------------------------------------------

class LegacyCodeCategory(str, Enum):
    """Categories of legacy code to remove."""
    RUNTIME_PATH = "runtime_path"
    FEATURE_FLAG = "feature_flag"
    COMPARISON_MODE = "comparison_mode"
    PILOT_ROUTING = "pilot_routing"
    SERVICE_MODULE = "service_module"
    TEST_FILE = "test_file"
    CONFIG_MODULE = "config_module"
    API_IMPORT = "api_import"


@dataclass
class LegacyCodeItem:
    """A single piece of legacy code to be removed."""
    id: str
    file_path: str
    description: str
    category: LegacyCodeCategory
    removal_action: str
    risk_level: str = "low"  # low, medium, high
    notes: str = ""


def get_legacy_code_inventory() -> List[LegacyCodeItem]:
    """Return the complete inventory of legacy code to remove.

    Each item identifies the file, what to remove, and the risk level.
    Items are ordered by recommended removal sequence.
    """
    return [
        # --- Feature flags in config ---
        LegacyCodeItem(
            id="LEG-01",
            file_path="app/config.py",
            description="USE_CE_CHAT_RUNTIME feature flag",
            category=LegacyCodeCategory.FEATURE_FLAG,
            removal_action=(
                "Remove USE_CE_CHAT_RUNTIME setting. CE runtime becomes "
                "the only path — no flag needed."
            ),
            risk_level="medium",
        ),
        LegacyCodeItem(
            id="LEG-02",
            file_path="app/config.py",
            description="LEGACY_CHAT_ENABLED feature flag",
            category=LegacyCodeCategory.FEATURE_FLAG,
            removal_action="Remove LEGACY_CHAT_ENABLED setting.",
            risk_level="medium",
        ),
        LegacyCodeItem(
            id="LEG-03",
            file_path="app/config.py",
            description="ENABLE_RUNTIME_COMPARISON feature flag",
            category=LegacyCodeCategory.FEATURE_FLAG,
            removal_action="Remove ENABLE_RUNTIME_COMPARISON setting.",
            risk_level="low",
        ),
        LegacyCodeItem(
            id="LEG-04",
            file_path="app/config.py",
            description="PILOT_USER_IDS and PILOT_ROLLOUT_ENABLED settings",
            category=LegacyCodeCategory.FEATURE_FLAG,
            removal_action=(
                "Remove PILOT_USER_IDS, PILOT_ROLLOUT_ENABLED settings "
                "and the pilot_user_ids_set property."
            ),
            risk_level="low",
        ),
        # --- ChatMessageHandler legacy paths ---
        LegacyCodeItem(
            id="LEG-05",
            file_path="app/services/chat_message_handler.py",
            description="_handle_legacy() method",
            category=LegacyCodeCategory.RUNTIME_PATH,
            removal_action=(
                "Delete the entire _handle_legacy() method. Remove the "
                "lazy import of ChatService inside it."
            ),
            risk_level="medium",
        ),
        LegacyCodeItem(
            id="LEG-06",
            file_path="app/services/chat_message_handler.py",
            description="_handle_comparison() method",
            category=LegacyCodeCategory.COMPARISON_MODE,
            removal_action=(
                "Delete the entire _handle_comparison() method and the "
                "import of run_comparison."
            ),
            risk_level="low",
        ),
        LegacyCodeItem(
            id="LEG-07",
            file_path="app/services/chat_message_handler.py",
            description="Dual runtime selection logic in __init__ and handle_message",
            category=LegacyCodeCategory.RUNTIME_PATH,
            removal_action=(
                "Simplify __init__ to always use CE path (remove runtime "
                "selection, PilotUserRegistry dependency, and the "
                "'runtime' attribute). Simplify handle_message to always "
                "call _handle_ce. Remove comparison-mode branch."
            ),
            risk_level="high",
            notes="This is the highest-risk change. Test thoroughly.",
        ),
        # --- Entire legacy service modules ---
        LegacyCodeItem(
            id="LEG-08",
            file_path="app/services/chat_service.py",
            description="Legacy ChatService (entire file)",
            category=LegacyCodeCategory.SERVICE_MODULE,
            removal_action=(
                "Delete the entire file. Contains legacy _get_system_prompt, "
                "get_chat_response, stream_chat_response, and fallback logic."
            ),
            risk_level="medium",
            notes="Verify no other module imports ChatService first.",
        ),
        LegacyCodeItem(
            id="LEG-09",
            file_path="app/services/runtime_comparison.py",
            description="Runtime comparison module (entire file)",
            category=LegacyCodeCategory.COMPARISON_MODE,
            removal_action="Delete the entire file.",
            risk_level="low",
        ),
        LegacyCodeItem(
            id="LEG-10",
            file_path="app/services/pilot_rollout.py",
            description="Pilot rollout module (entire file)",
            category=LegacyCodeCategory.PILOT_ROUTING,
            removal_action="Delete the entire file.",
            risk_level="low",
        ),
        # --- API layer legacy imports ---
        LegacyCodeItem(
            id="LEG-11",
            file_path="app/api/chat.py",
            description="Fallback import of ChatService (lines 20-25)",
            category=LegacyCodeCategory.API_IMPORT,
            removal_action=(
                "Remove the try/except import block that falls back to "
                "ChatService when LangChain is unavailable. The CE path "
                "does not use ChatService."
            ),
            risk_level="low",
        ),
        # --- Config modules ---
        LegacyCodeItem(
            id="LEG-12",
            file_path="app/config/rollout_config.py",
            description="Rollout configuration module (entire file)",
            category=LegacyCodeCategory.CONFIG_MODULE,
            removal_action=(
                "Delete the entire file after rollout is complete. "
                "Rollout checklist, pilot group config, rollback procedure, "
                "and dashboard spec are no longer needed."
            ),
            risk_level="low",
            notes="Archive to docs/ if historical reference is desired.",
        ),
        # --- Test files ---
        LegacyCodeItem(
            id="LEG-13",
            file_path="tests/test_dual_runtime_support.py",
            description="Dual runtime support tests (entire file)",
            category=LegacyCodeCategory.TEST_FILE,
            removal_action="Delete the entire file.",
            risk_level="low",
        ),
        LegacyCodeItem(
            id="LEG-14",
            file_path="tests/test_runtime_comparison.py",
            description="Runtime comparison tests (entire file)",
            category=LegacyCodeCategory.TEST_FILE,
            removal_action="Delete the entire file.",
            risk_level="low",
        ),
        LegacyCodeItem(
            id="LEG-15",
            file_path="tests/test_pilot_rollout.py",
            description="Pilot rollout tests (entire file)",
            category=LegacyCodeCategory.TEST_FILE,
            removal_action="Delete the entire file.",
            risk_level="low",
        ),
        LegacyCodeItem(
            id="LEG-16",
            file_path="tests/test_quality_validation.py",
            description="Legacy baseline comparison tests within quality validation",
            category=LegacyCodeCategory.TEST_FILE,
            removal_action=(
                "Remove TestLegacyBaselineComparison class and any tests "
                "that reference the legacy runtime path."
            ),
            risk_level="low",
        ),
        # --- Environment files ---
        LegacyCodeItem(
            id="LEG-17",
            file_path=".env / .env.example / .env.template",
            description="Legacy feature flag environment variables",
            category=LegacyCodeCategory.FEATURE_FLAG,
            removal_action=(
                "Remove USE_CE_CHAT_RUNTIME, LEGACY_CHAT_ENABLED, "
                "ENABLE_RUNTIME_COMPARISON, PILOT_ROLLOUT_ENABLED, "
                "and PILOT_USER_IDS from all env files."
            ),
            risk_level="low",
        ),
    ]


# ---------------------------------------------------------------------------
# 6.7.3 – Stability Requirements
# ---------------------------------------------------------------------------

@dataclass
class StabilityRequirement:
    """A single stability criterion that must be met before legacy removal."""
    id: str
    metric: str
    threshold: str
    measurement_window: str
    description: str


def get_stability_requirements() -> List[StabilityRequirement]:
    """Return the stability requirements for legacy code removal.

    All requirements must be met for 14 consecutive days under full
    production traffic on the CE runtime before legacy code is removed.
    """
    return [
        StabilityRequirement(
            id="STAB-01",
            metric="error_rate",
            threshold="< 1%",
            measurement_window="rolling 24-hour window, 14 consecutive days",
            description=(
                "CE runtime error rate must remain below 1% across all "
                "chat requests for 14 consecutive days."
            ),
        ),
        StabilityRequirement(
            id="STAB-02",
            metric="p95_latency_simple",
            threshold="< 3000 ms",
            measurement_window="rolling 24-hour window, 14 consecutive days",
            description=(
                "p95 latency for simple (no-tool) queries must stay "
                "below 3 seconds."
            ),
        ),
        StabilityRequirement(
            id="STAB-03",
            metric="p95_latency_multi_tool",
            threshold="< 5000 ms",
            measurement_window="rolling 24-hour window, 14 consecutive days",
            description=(
                "p95 latency for multi-tool queries must stay below "
                "5 seconds."
            ),
        ),
        StabilityRequirement(
            id="STAB-04",
            metric="fallback_rate",
            threshold="< 10%",
            measurement_window="rolling 24-hour window, 14 consecutive days",
            description=(
                "LLM fallback model usage must remain below 10%."
            ),
        ),
        StabilityRequirement(
            id="STAB-05",
            metric="tool_success_rate",
            threshold=">= 95%",
            measurement_window="rolling 24-hour window, 14 consecutive days",
            description=(
                "Tool execution success rate must be at least 95%."
            ),
        ),
        StabilityRequirement(
            id="STAB-06",
            metric="token_budget_compliance",
            threshold="100%",
            measurement_window="all requests over 14 days",
            description=(
                "All requests must stay within the 2400-token context "
                "budget. Zero budget violations allowed."
            ),
        ),
        StabilityRequirement(
            id="STAB-07",
            metric="session_data_integrity",
            threshold="zero incidents",
            measurement_window="14 consecutive days",
            description=(
                "No session data corruption, cross-session leakage, "
                "or message loss incidents."
            ),
        ),
        StabilityRequirement(
            id="STAB-08",
            metric="zero_critical_bugs",
            threshold="zero open critical/high bugs",
            measurement_window="at time of removal decision",
            description=(
                "No open critical or high severity bugs related to the "
                "CE chat runtime at the time legacy removal begins."
            ),
        ),
    ]


STABILITY_WINDOW_DAYS: int = 14
"""Number of consecutive days all stability requirements must hold."""


# ---------------------------------------------------------------------------
# 6.7.4 – Rollback Procedure (during deprecation)
# ---------------------------------------------------------------------------

@dataclass
class RollbackStep:
    """A single step in the rollback procedure."""
    order: int
    action: str
    command: str
    verification: str


@dataclass
class DeprecationRollbackProcedure:
    """Rollback procedure specific to the deprecation/removal phases.

    This extends the pilot-phase rollback (in rollout_config.py) to cover
    scenarios that arise *after* legacy code has been disabled or removed.
    """
    phase: str
    description: str
    steps: List[RollbackStep] = field(default_factory=list)


def get_deprecation_rollback_procedures() -> List[DeprecationRollbackProcedure]:
    """Return rollback procedures for each deprecation phase."""
    return [
        # Rollback during stability observation (DEP-03)
        DeprecationRollbackProcedure(
            phase="stability-observation",
            description=(
                "CE is live for all users but legacy code is still present. "
                "Rollback is straightforward: flip the feature flag."
            ),
            steps=[
                RollbackStep(
                    order=1,
                    action="Set USE_CE_CHAT_RUNTIME=false",
                    command="Update .env: USE_CE_CHAT_RUNTIME=false",
                    verification="Confirm logs show runtime=legacy",
                ),
                RollbackStep(
                    order=2,
                    action="Restart application",
                    command="Restart the application service",
                    verification="Health check returns 200",
                ),
                RollbackStep(
                    order=3,
                    action="Verify legacy path functional",
                    command="Send test chat message",
                    verification="Response has runtime=legacy",
                ),
            ],
        ),
        # Rollback during soft deprecation (DEP-04)
        DeprecationRollbackProcedure(
            phase="soft-deprecation",
            description=(
                "LEGACY_CHAT_ENABLED=false but code still present. "
                "Re-enable the flag to restore legacy path."
            ),
            steps=[
                RollbackStep(
                    order=1,
                    action="Set LEGACY_CHAT_ENABLED=true",
                    command="Update .env: LEGACY_CHAT_ENABLED=true",
                    verification="Confirm setting reads true",
                ),
                RollbackStep(
                    order=2,
                    action="Set USE_CE_CHAT_RUNTIME=false",
                    command="Update .env: USE_CE_CHAT_RUNTIME=false",
                    verification="Confirm logs show runtime=legacy",
                ),
                RollbackStep(
                    order=3,
                    action="Restart application",
                    command="Restart the application service",
                    verification="Health check returns 200",
                ),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Post-removal rollback (DEP-05 already executed — code is gone)
# ---------------------------------------------------------------------------

POST_REMOVAL_ROLLBACK_NOTE: str = (
    "Once legacy code has been removed (DEP-05), a feature-flag rollback "
    "is no longer possible. The rollback strategy at this stage is to "
    "revert the removal commit via git:\n"
    "  1. git revert <removal-commit-sha>\n"
    "  2. Redeploy the reverted build\n"
    "  3. Set USE_CE_CHAT_RUNTIME=false and LEGACY_CHAT_ENABLED=true\n"
    "  4. Restart and verify legacy path is functional\n"
    "This is why the removal is done in a single, well-scoped commit."
)


# ---------------------------------------------------------------------------
# 6.7.5 – Removal Checklist
# ---------------------------------------------------------------------------

class RemovalStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"


@dataclass
class RemovalChecklistItem:
    """A single item on the legacy code removal checklist."""
    order: int
    id: str
    action: str
    file_path: str
    verification: str
    status: RemovalStatus = RemovalStatus.PENDING
    legacy_items: List[str] = field(default_factory=list)


def get_removal_checklist() -> List[RemovalChecklistItem]:
    """Return the ordered checklist for removing all legacy code.

    Items are ordered to minimise breakage: tests first, then
    service modules, then handler refactor, then config cleanup.
    """
    return [
        # Step 1 – Remove legacy test files
        RemovalChecklistItem(
            order=1,
            id="RM-01",
            action="Delete legacy test files",
            file_path="tests/",
            verification="pytest runs without import errors",
            legacy_items=[
                "tests/test_dual_runtime_support.py",
                "tests/test_runtime_comparison.py",
                "tests/test_pilot_rollout.py",
            ],
        ),
        # Step 2 – Remove legacy service modules
        RemovalChecklistItem(
            order=2,
            id="RM-02",
            action="Delete legacy service modules",
            file_path="app/services/",
            verification="No import errors in remaining modules",
            legacy_items=[
                "app/services/chat_service.py",
                "app/services/runtime_comparison.py",
                "app/services/pilot_rollout.py",
            ],
        ),
        # Step 3 – Simplify ChatMessageHandler
        RemovalChecklistItem(
            order=3,
            id="RM-03",
            action=(
                "Remove _handle_legacy(), _handle_comparison(), "
                "dual-runtime __init__ logic, PilotUserRegistry dep, "
                "and 'runtime' attribute from ChatMessageHandler"
            ),
            file_path="app/services/chat_message_handler.py",
            verification=(
                "Handler always delegates to ChatAgent. "
                "No 'legacy' or 'comparison' code paths remain."
            ),
        ),
        # Step 4 – Clean up API imports
        RemovalChecklistItem(
            order=4,
            id="RM-04",
            action=(
                "Remove try/except ChatService fallback import "
                "from app/api/chat.py"
            ),
            file_path="app/api/chat.py",
            verification="API module imports cleanly without ChatService",
        ),
        # Step 5 – Remove feature flags from config
        RemovalChecklistItem(
            order=5,
            id="RM-05",
            action=(
                "Remove USE_CE_CHAT_RUNTIME, LEGACY_CHAT_ENABLED, "
                "ENABLE_RUNTIME_COMPARISON, PILOT_ROLLOUT_ENABLED, "
                "PILOT_USER_IDS from Settings and pilot_user_ids_set property"
            ),
            file_path="app/config.py",
            verification="Settings class has no legacy/pilot fields",
        ),
        # Step 6 – Remove rollout config module
        RemovalChecklistItem(
            order=6,
            id="RM-06",
            action="Delete rollout configuration module",
            file_path="app/config/rollout_config.py",
            verification="No imports of rollout_config remain",
        ),
        # Step 7 – Remove this deprecation plan module
        RemovalChecklistItem(
            order=7,
            id="RM-07",
            action="Delete legacy deprecation plan module",
            file_path="app/config/legacy_deprecation_plan.py",
            verification="No imports of legacy_deprecation_plan remain",
        ),
        # Step 8 – Clean environment files
        RemovalChecklistItem(
            order=8,
            id="RM-08",
            action=(
                "Remove legacy feature flag variables from "
                ".env, .env.example, .env.template"
            ),
            file_path=".env*",
            verification="No legacy flag variables in env files",
        ),
        # Step 9 – Update remaining tests
        RemovalChecklistItem(
            order=9,
            id="RM-09",
            action=(
                "Update tests that reference legacy settings "
                "(LEGACY_CHAT_ENABLED, USE_CE_CHAT_RUNTIME) to "
                "remove those parameters"
            ),
            file_path="tests/",
            verification="Full test suite passes with no legacy references",
            legacy_items=[
                "tests/test_quality_validation.py",
                "tests/test_phase2_exit_criteria.py",
                "tests/test_phase2_exit_validation.py",
                "tests/test_performance_monitoring.py",
                "tests/test_task_17_1_rag_chat_integration.py",
            ],
        ),
        # Step 10 – Final validation
        RemovalChecklistItem(
            order=10,
            id="RM-10",
            action=(
                "Run full test suite, verify 85% coverage on CE "
                "components, confirm no 'legacy' references in "
                "production code"
            ),
            file_path="(entire codebase)",
            verification=(
                "pytest passes, coverage >= 85%, "
                "grep -r 'legacy' app/ returns zero hits"
            ),
        ),
    ]
