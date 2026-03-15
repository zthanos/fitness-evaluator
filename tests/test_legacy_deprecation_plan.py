"""Tests for Legacy Deprecation Plan (Phase 6, Task 6.7)

Validates the deprecation timeline, legacy code inventory, stability
requirements, rollback procedures, and removal checklist are complete
and internally consistent.

Requirements: 6.4 (Legacy Path Deprecation)
"""
import pytest

from app.config.legacy_deprecation_plan import (
    STABILITY_WINDOW_DAYS,
    POST_REMOVAL_ROLLBACK_NOTE,
    DeprecationMilestone,
    LegacyCodeCategory,
    LegacyCodeItem,
    MilestoneStatus,
    RemovalChecklistItem,
    RemovalStatus,
    StabilityRequirement,
    get_deprecation_timeline,
    get_legacy_code_inventory,
    get_stability_requirements,
    get_deprecation_rollback_procedures,
    get_removal_checklist,
)


# ---------------------------------------------------------------------------
# 6.7.1 – Timeline
# ---------------------------------------------------------------------------

class TestDeprecationTimeline:
    def test_timeline_has_all_phases(self):
        timeline = get_deprecation_timeline()
        phases = [m.phase for m in timeline]
        assert "pilot" in phases
        assert "general-availability" in phases
        assert "stability-observation" in phases
        assert "soft-deprecation" in phases
        assert "code-removal" in phases
        assert "post-removal" in phases

    def test_timeline_ordered_by_id(self):
        timeline = get_deprecation_timeline()
        ids = [m.id for m in timeline]
        assert ids == sorted(ids)

    def test_stability_observation_is_14_days(self):
        timeline = get_deprecation_timeline()
        stability = [m for m in timeline if m.phase == "stability-observation"]
        assert len(stability) == 1
        assert stability[0].duration_days == 14

    def test_each_milestone_has_prerequisites(self):
        timeline = get_deprecation_timeline()
        # First milestone has external prerequisites, rest reference prior milestones
        for m in timeline[1:]:
            assert len(m.prerequisites) > 0, f"{m.id} has no prerequisites"

    def test_milestones_default_to_not_started(self):
        timeline = get_deprecation_timeline()
        for m in timeline:
            assert m.status == MilestoneStatus.NOT_STARTED


# ---------------------------------------------------------------------------
# 6.7.2 – Legacy Code Inventory
# ---------------------------------------------------------------------------

class TestLegacyCodeInventory:
    def test_inventory_not_empty(self):
        inventory = get_legacy_code_inventory()
        assert len(inventory) > 0

    def test_all_items_have_file_path(self):
        for item in get_legacy_code_inventory():
            assert item.file_path, f"{item.id} missing file_path"

    def test_all_items_have_removal_action(self):
        for item in get_legacy_code_inventory():
            assert item.removal_action, f"{item.id} missing removal_action"

    def test_feature_flags_identified(self):
        inventory = get_legacy_code_inventory()
        flag_items = [
            i for i in inventory
            if i.category == LegacyCodeCategory.FEATURE_FLAG
        ]
        descriptions = " ".join(i.description for i in flag_items)
        assert "USE_CE_CHAT_RUNTIME" in descriptions
        assert "LEGACY_CHAT_ENABLED" in descriptions
        assert "ENABLE_RUNTIME_COMPARISON" in descriptions
        assert "PILOT_ROLLOUT_ENABLED" in descriptions

    def test_legacy_handler_methods_identified(self):
        inventory = get_legacy_code_inventory()
        handler_items = [
            i for i in inventory
            if "chat_message_handler" in i.file_path
        ]
        descriptions = " ".join(i.description for i in handler_items)
        assert "_handle_legacy" in descriptions
        assert "_handle_comparison" in descriptions

    def test_legacy_service_modules_identified(self):
        inventory = get_legacy_code_inventory()
        paths = [i.file_path for i in inventory]
        assert "app/services/chat_service.py" in paths
        assert "app/services/runtime_comparison.py" in paths
        assert "app/services/pilot_rollout.py" in paths

    def test_legacy_test_files_identified(self):
        inventory = get_legacy_code_inventory()
        test_items = [
            i for i in inventory
            if i.category == LegacyCodeCategory.TEST_FILE
        ]
        paths = [i.file_path for i in test_items]
        assert any("test_dual_runtime" in p for p in paths)
        assert any("test_runtime_comparison" in p for p in paths)
        assert any("test_pilot_rollout" in p for p in paths)

    def test_unique_ids(self):
        inventory = get_legacy_code_inventory()
        ids = [i.id for i in inventory]
        assert len(ids) == len(set(ids)), "Duplicate IDs found"


# ---------------------------------------------------------------------------
# 6.7.3 – Stability Requirements
# ---------------------------------------------------------------------------

class TestStabilityRequirements:
    def test_stability_window_is_14_days(self):
        assert STABILITY_WINDOW_DAYS == 14

    def test_requirements_not_empty(self):
        reqs = get_stability_requirements()
        assert len(reqs) > 0

    def test_error_rate_requirement_exists(self):
        reqs = get_stability_requirements()
        metrics = [r.metric for r in reqs]
        assert "error_rate" in metrics

    def test_latency_requirements_exist(self):
        reqs = get_stability_requirements()
        metrics = [r.metric for r in reqs]
        assert "p95_latency_simple" in metrics
        assert "p95_latency_multi_tool" in metrics

    def test_all_requirements_have_threshold(self):
        for req in get_stability_requirements():
            assert req.threshold, f"{req.id} missing threshold"

    def test_all_requirements_have_measurement_window(self):
        for req in get_stability_requirements():
            assert req.measurement_window, f"{req.id} missing window"

    def test_unique_ids(self):
        reqs = get_stability_requirements()
        ids = [r.id for r in reqs]
        assert len(ids) == len(set(ids))

    def test_session_integrity_requirement_exists(self):
        reqs = get_stability_requirements()
        metrics = [r.metric for r in reqs]
        assert "session_data_integrity" in metrics

    def test_zero_critical_bugs_requirement(self):
        reqs = get_stability_requirements()
        bug_reqs = [r for r in reqs if r.metric == "zero_critical_bugs"]
        assert len(bug_reqs) == 1
        assert "zero" in bug_reqs[0].threshold.lower()


# ---------------------------------------------------------------------------
# 6.7.4 – Rollback Procedure
# ---------------------------------------------------------------------------

class TestRollbackProcedure:
    def test_procedures_cover_key_phases(self):
        procs = get_deprecation_rollback_procedures()
        phases = [p.phase for p in procs]
        assert "stability-observation" in phases
        assert "soft-deprecation" in phases

    def test_each_procedure_has_steps(self):
        for proc in get_deprecation_rollback_procedures():
            assert len(proc.steps) > 0, f"{proc.phase} has no steps"

    def test_steps_are_ordered(self):
        for proc in get_deprecation_rollback_procedures():
            orders = [s.order for s in proc.steps]
            assert orders == sorted(orders)

    def test_post_removal_rollback_documented(self):
        assert "git revert" in POST_REMOVAL_ROLLBACK_NOTE
        assert "single" in POST_REMOVAL_ROLLBACK_NOTE.lower()


# ---------------------------------------------------------------------------
# 6.7.5 – Removal Checklist
# ---------------------------------------------------------------------------

class TestRemovalChecklist:
    def test_checklist_not_empty(self):
        checklist = get_removal_checklist()
        assert len(checklist) > 0

    def test_checklist_ordered(self):
        checklist = get_removal_checklist()
        orders = [item.order for item in checklist]
        assert orders == sorted(orders)

    def test_all_items_have_verification(self):
        for item in get_removal_checklist():
            assert item.verification, f"{item.id} missing verification"

    def test_all_items_default_to_pending(self):
        for item in get_removal_checklist():
            assert item.status == RemovalStatus.PENDING

    def test_tests_removed_before_services(self):
        checklist = get_removal_checklist()
        test_item = next(i for i in checklist if i.id == "RM-01")
        service_item = next(i for i in checklist if i.id == "RM-02")
        assert test_item.order < service_item.order

    def test_handler_simplified_before_config_cleanup(self):
        checklist = get_removal_checklist()
        handler_item = next(i for i in checklist if i.id == "RM-03")
        config_item = next(i for i in checklist if i.id == "RM-05")
        assert handler_item.order < config_item.order

    def test_final_validation_is_last(self):
        checklist = get_removal_checklist()
        last = max(checklist, key=lambda i: i.order)
        assert "full test suite" in last.action.lower()

    def test_unique_ids(self):
        checklist = get_removal_checklist()
        ids = [i.id for i in checklist]
        assert len(ids) == len(set(ids))

    def test_checklist_covers_all_inventory_categories(self):
        """Verify the checklist addresses every category in the inventory."""
        inventory = get_legacy_code_inventory()
        categories = {i.category for i in inventory}
        checklist = get_removal_checklist()
        all_actions = " ".join(item.action for item in checklist)
        all_files = " ".join(item.file_path for item in checklist)
        combined = all_actions + " " + all_files

        # Each category should be addressed somewhere in the checklist
        for cat in categories:
            if cat == LegacyCodeCategory.RUNTIME_PATH:
                assert "handle_legacy" in combined.lower() or "handler" in combined.lower()
            elif cat == LegacyCodeCategory.FEATURE_FLAG:
                assert "USE_CE_CHAT_RUNTIME" in combined or "feature flag" in combined.lower()
            elif cat == LegacyCodeCategory.SERVICE_MODULE:
                assert "chat_service" in combined.lower() or "service module" in combined.lower()
            elif cat == LegacyCodeCategory.TEST_FILE:
                assert "test" in combined.lower()
