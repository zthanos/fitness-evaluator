"""
Tests for CE Chat Runtime Rollout Configuration (Task 6.4).

Validates:
- 6.4.1 Rollout checklist completeness
- 6.4.2 Pilot user group configuration
- 6.4.3 Success metrics and evaluation
- 6.4.4 Rollback procedure triggers and steps
- 6.4.5 Monitoring dashboard requirements
"""

import pytest

from app.config.rollout_config import (
    ChecklistItem,
    ChecklistItemStatus,
    DashboardSpec,
    DashboardWidget,
    PilotGroupConfig,
    RollbackProcedure,
    RollbackSeverity,
    RollbackTrigger,
    SuccessMetrics,
    WidgetType,
    build_pilot_user_query_filter,
    evaluate_metric,
    get_monitoring_dashboard_spec,
    get_pilot_group_config,
    get_rollback_procedure,
    get_rollout_checklist,
    get_success_metrics,
)


# ---------------------------------------------------------------------------
# 6.4.1 – Rollout Checklist
# ---------------------------------------------------------------------------

class TestRolloutChecklist:
    def test_checklist_not_empty(self):
        checklist = get_rollout_checklist()
        assert len(checklist) > 0

    def test_checklist_covers_all_phases(self):
        checklist = get_rollout_checklist()
        phases = {item.phase for item in checklist}
        assert "pre-rollout" in phases
        assert "pilot" in phases
        assert "general-availability" in phases

    def test_checklist_items_have_unique_ids(self):
        checklist = get_rollout_checklist()
        ids = [item.id for item in checklist]
        assert len(ids) == len(set(ids))

    def test_checklist_items_have_descriptions(self):
        checklist = get_rollout_checklist()
        for item in checklist:
            assert item.description, f"Item {item.id} missing description"

    def test_checklist_default_status_is_not_started(self):
        checklist = get_rollout_checklist()
        for item in checklist:
            assert item.status == ChecklistItemStatus.NOT_STARTED

    def test_pre_rollout_includes_feature_flag_check(self):
        checklist = get_rollout_checklist()
        pre_items = [i for i in checklist if i.phase == "pre-rollout"]
        descriptions = " ".join(i.description for i in pre_items)
        assert "feature flag" in descriptions.lower() or "USE_CE_CHAT_RUNTIME" in descriptions

    def test_pre_rollout_includes_rollback_check(self):
        checklist = get_rollout_checklist()
        pre_items = [i for i in checklist if i.phase == "pre-rollout"]
        descriptions = " ".join(i.description.lower() for i in pre_items)
        assert "rollback" in descriptions

    def test_ga_includes_legacy_removal(self):
        checklist = get_rollout_checklist()
        ga_items = [i for i in checklist if i.phase == "general-availability"]
        descriptions = " ".join(i.description.lower() for i in ga_items)
        assert "legacy" in descriptions


# ---------------------------------------------------------------------------
# 6.4.2 – Pilot User Group
# ---------------------------------------------------------------------------

class TestPilotUserGroup:
    def test_default_config_values(self):
        config = get_pilot_group_config()
        assert config.min_sessions_last_30_days == 5
        assert config.max_pilot_users == 20
        assert config.min_pilot_users == 5
        assert config.pilot_duration_days == 14

    def test_pilot_includes_diverse_users(self):
        config = get_pilot_group_config()
        assert config.include_tool_heavy_users is True
        assert config.include_simple_query_users is True

    def test_excludes_very_new_users(self):
        config = get_pilot_group_config()
        assert config.exclude_new_users_days >= 7

    def test_query_filter_contains_required_keys(self):
        config = get_pilot_group_config()
        query_filter = build_pilot_user_query_filter(config)
        assert "min_sessions_last_30_days" in query_filter
        assert "exclude_new_users_days" in query_filter
        assert "max_results" in query_filter
        assert "description" in query_filter

    def test_query_filter_max_results_matches_config(self):
        config = PilotGroupConfig(max_pilot_users=10)
        query_filter = build_pilot_user_query_filter(config)
        assert query_filter["max_results"] == 10


# ---------------------------------------------------------------------------
# 6.4.3 – Success Metrics
# ---------------------------------------------------------------------------

class TestSuccessMetrics:
    def test_default_latency_targets(self):
        m = get_success_metrics()
        assert m.p95_latency_simple_ms == 3000.0
        assert m.p95_latency_multi_tool_ms == 5000.0
        assert m.context_build_latency_ms == 500.0
        assert m.rag_retrieval_latency_ms == 200.0

    def test_default_reliability_targets(self):
        m = get_success_metrics()
        assert m.error_rate_threshold == 0.01
        assert m.fallback_rate_threshold == 0.10
        assert m.tool_success_rate_min == 0.95

    def test_stability_window(self):
        m = get_success_metrics()
        assert m.stability_window_days == 14

    def test_evaluate_metric_latency_pass(self):
        assert evaluate_metric("p95_latency_simple_ms", 2500.0) is True

    def test_evaluate_metric_latency_fail(self):
        assert evaluate_metric("p95_latency_simple_ms", 4000.0) is False

    def test_evaluate_metric_error_rate_pass(self):
        assert evaluate_metric("error_rate_threshold", 0.005) is True

    def test_evaluate_metric_error_rate_fail(self):
        assert evaluate_metric("error_rate_threshold", 0.02) is False

    def test_evaluate_metric_min_quality_pass(self):
        assert evaluate_metric("min_quality_parity", 0.98) is True

    def test_evaluate_metric_min_quality_fail(self):
        assert evaluate_metric("min_quality_parity", 0.90) is False

    def test_evaluate_metric_tool_success_rate_pass(self):
        assert evaluate_metric("tool_success_rate_min", 0.97) is True

    def test_evaluate_metric_tool_success_rate_fail(self):
        assert evaluate_metric("tool_success_rate_min", 0.80) is False

    def test_evaluate_metric_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown metric"):
            evaluate_metric("nonexistent_metric", 1.0)

    def test_evaluate_metric_stability_window(self):
        assert evaluate_metric("stability_window_days", 14) is True
        assert evaluate_metric("stability_window_days", 7) is False


# ---------------------------------------------------------------------------
# 6.4.4 – Rollback Procedure
# ---------------------------------------------------------------------------

class TestRollbackProcedure:
    def test_procedure_has_triggers(self):
        proc = get_rollback_procedure()
        assert len(proc.triggers) > 0

    def test_procedure_has_steps(self):
        proc = get_rollback_procedure()
        assert len(proc.steps) > 0

    def test_triggers_have_unique_ids(self):
        proc = get_rollback_procedure()
        ids = [t.id for t in proc.triggers]
        assert len(ids) == len(set(ids))

    def test_triggers_include_critical_severity(self):
        proc = get_rollback_procedure()
        severities = {t.severity for t in proc.triggers}
        assert RollbackSeverity.CRITICAL in severities

    def test_triggers_cover_error_rate(self):
        proc = get_rollback_procedure()
        metric_names = [t.metric_name for t in proc.triggers]
        assert "error_rate_threshold" in metric_names

    def test_triggers_cover_latency(self):
        proc = get_rollback_procedure()
        metric_names = [t.metric_name for t in proc.triggers]
        assert "p95_latency_simple_ms" in metric_names

    def test_triggers_cover_data_integrity(self):
        proc = get_rollback_procedure()
        metric_names = [t.metric_name for t in proc.triggers]
        assert "session_data_integrity" in metric_names

    def test_steps_are_ordered(self):
        proc = get_rollback_procedure()
        orders = [s.order for s in proc.steps]
        assert orders == sorted(orders)

    def test_first_step_disables_ce_runtime(self):
        proc = get_rollback_procedure()
        first_step = proc.steps[0]
        assert "USE_CE_CHAT_RUNTIME" in first_step.action or "USE_CE_CHAT_RUNTIME" in first_step.command

    def test_steps_include_verification(self):
        proc = get_rollback_procedure()
        for step in proc.steps:
            assert step.verification, f"Step {step.order} missing verification"

    def test_steps_include_team_notification(self):
        proc = get_rollback_procedure()
        actions = " ".join(s.action.lower() for s in proc.steps)
        assert "notify" in actions


# ---------------------------------------------------------------------------
# 6.4.5 – Monitoring Dashboard Requirements
# ---------------------------------------------------------------------------

class TestMonitoringDashboard:
    def test_dashboard_has_name(self):
        spec = get_monitoring_dashboard_spec()
        assert spec.name

    def test_dashboard_has_widgets(self):
        spec = get_monitoring_dashboard_spec()
        assert len(spec.widgets) > 0

    def test_widgets_have_unique_ids(self):
        spec = get_monitoring_dashboard_spec()
        ids = [w.id for w in spec.widgets]
        assert len(ids) == len(set(ids))

    def test_widgets_cover_latency(self):
        spec = get_monitoring_dashboard_spec()
        ids = [w.id for w in spec.widgets]
        assert "latency-p95" in ids

    def test_widgets_cover_error_rate(self):
        spec = get_monitoring_dashboard_spec()
        ids = [w.id for w in spec.widgets]
        assert "error-rate" in ids

    def test_widgets_cover_fallback(self):
        spec = get_monitoring_dashboard_spec()
        ids = [w.id for w in spec.widgets]
        assert "fallback-rate" in ids

    def test_widgets_cover_token_usage(self):
        spec = get_monitoring_dashboard_spec()
        ids = [w.id for w in spec.widgets]
        assert "token-usage" in ids

    def test_widgets_cover_tool_success(self):
        spec = get_monitoring_dashboard_spec()
        ids = [w.id for w in spec.widgets]
        assert "tool-success-rate" in ids

    def test_widgets_reference_telemetry_source(self):
        spec = get_monitoring_dashboard_spec()
        for w in spec.widgets:
            assert "jsonl" in w.data_source, f"Widget {w.id} missing telemetry source"

    def test_critical_widgets_have_alert_thresholds(self):
        spec = get_monitoring_dashboard_spec()
        critical_ids = {"latency-p95", "error-rate", "fallback-rate", "tool-success-rate"}
        for w in spec.widgets:
            if w.id in critical_ids:
                assert w.alert_threshold, f"Widget {w.id} missing alert threshold"
