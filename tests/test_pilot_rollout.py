"""
Tests for Pilot Rollout Service (Phase 6.6).

Covers:
- 6.6.1 Pilot user feature flag / per-user CE enablement
- 6.6.2 Pilot telemetry monitoring
- 6.6.3 User feedback collection
- 6.6.4 Bug identification and tracking
- 6.6.5 Quality iteration support
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from app.config import Settings
from app.services.pilot_rollout import (
    PilotUserRegistry,
    PilotTelemetryMonitor,
    PilotTelemetrySnapshot,
    FeedbackCollector,
    FeedbackRating,
    BugTracker,
    BugSeverity,
    BugStatus,
    QualityGate,
    QualityThreshold,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides) -> Settings:
    """Create a Settings instance with test defaults."""
    defaults = {
        "USE_CE_CHAT_RUNTIME": False,
        "LEGACY_CHAT_ENABLED": True,
        "PILOT_ROLLOUT_ENABLED": False,
        "PILOT_USER_IDS": "",
        "OLLAMA_ENDPOINT": "http://localhost:11434",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ===================================================================
# 6.6.1 – Pilot User Feature Flag
# ===================================================================

class TestPilotUserRegistry:
    """Tests for per-user CE runtime enablement."""

    def test_pilot_disabled_returns_false(self):
        settings = _make_settings(PILOT_ROLLOUT_ENABLED=False, PILOT_USER_IDS="1,2,3")
        registry = PilotUserRegistry(settings)
        assert not registry.is_pilot_user(1)

    def test_pilot_enabled_with_matching_user(self):
        settings = _make_settings(PILOT_ROLLOUT_ENABLED=True, PILOT_USER_IDS="10,20,30")
        registry = PilotUserRegistry(settings)
        assert registry.is_pilot_user(10)
        assert registry.is_pilot_user(20)
        assert not registry.is_pilot_user(99)

    def test_runtime_add_user(self):
        settings = _make_settings(PILOT_ROLLOUT_ENABLED=True, PILOT_USER_IDS="")
        registry = PilotUserRegistry(settings)
        assert not registry.is_pilot_user(42)
        registry.add_pilot_user(42)
        assert registry.is_pilot_user(42)

    def test_runtime_remove_user(self):
        settings = _make_settings(PILOT_ROLLOUT_ENABLED=True, PILOT_USER_IDS="42")
        registry = PilotUserRegistry(settings)
        assert registry.is_pilot_user(42)
        registry.remove_pilot_user(42)
        assert not registry.is_pilot_user(42)

    def test_get_pilot_user_ids_combines_config_and_runtime(self):
        settings = _make_settings(PILOT_ROLLOUT_ENABLED=True, PILOT_USER_IDS="1,2")
        registry = PilotUserRegistry(settings)
        registry.add_pilot_user(3)
        registry.remove_pilot_user(2)
        assert registry.get_pilot_user_ids() == {1, 3}

    def test_should_use_ce_runtime_global_flag(self):
        settings = _make_settings(USE_CE_CHAT_RUNTIME=True, PILOT_ROLLOUT_ENABLED=False)
        registry = PilotUserRegistry(settings)
        # Global flag overrides pilot check
        assert registry.should_use_ce_runtime(999)

    def test_should_use_ce_runtime_pilot_user(self):
        settings = _make_settings(
            USE_CE_CHAT_RUNTIME=False,
            PILOT_ROLLOUT_ENABLED=True,
            PILOT_USER_IDS="42",
        )
        registry = PilotUserRegistry(settings)
        assert registry.should_use_ce_runtime(42)
        assert not registry.should_use_ce_runtime(99)

    def test_pilot_enabled_property(self):
        settings = _make_settings(PILOT_ROLLOUT_ENABLED=True)
        registry = PilotUserRegistry(settings)
        assert registry.pilot_enabled

    def test_empty_pilot_user_ids_parsed(self):
        settings = _make_settings(PILOT_USER_IDS="")
        assert settings.pilot_user_ids_set == set()

    def test_pilot_user_ids_with_spaces(self):
        settings = _make_settings(PILOT_USER_IDS=" 1 , 2 , 3 ")
        assert settings.pilot_user_ids_set == {1, 2, 3}


# ===================================================================
# 6.6.2 – Pilot Telemetry Monitoring
# ===================================================================

class TestPilotTelemetryMonitor:
    """Tests for pilot-group telemetry monitoring."""

    def _make_monitor(self, pilot_ids="10,20"):
        settings = _make_settings(PILOT_ROLLOUT_ENABLED=True, PILOT_USER_IDS=pilot_ids)
        registry = PilotUserRegistry(settings)
        return PilotTelemetryMonitor(registry)

    def test_record_event_tags_pilot_status(self):
        monitor = self._make_monitor()
        event = {"athlete_id": 10, "timestamp": datetime.utcnow().isoformat()}
        monitor.record_event(event)
        assert event["is_pilot"] is True
        assert event["pilot_group"] == "pilot"

    def test_record_event_tags_non_pilot(self):
        monitor = self._make_monitor()
        event = {"athlete_id": 99, "timestamp": datetime.utcnow().isoformat()}
        monitor.record_event(event)
        assert event["is_pilot"] is False
        assert event["pilot_group"] == "control"

    def test_snapshot_aggregates_pilot_metrics(self):
        monitor = self._make_monitor()
        now = datetime.utcnow().isoformat()
        for i in range(5):
            monitor.record_event({
                "athlete_id": 10,
                "timestamp": now,
                "total_latency_ms": 1000 + i * 100,
                "success_status": True,
                "fallback_used": False,
                "context_token_count": 200,
                "response_token_count": 100,
            })
        snapshot = monitor.get_pilot_snapshot(window_minutes=60)
        assert snapshot.pilot_requests == 5
        assert snapshot.avg_latency_ms > 0
        assert snapshot.error_rate == 0.0

    def test_snapshot_empty_when_no_events(self):
        monitor = self._make_monitor()
        snapshot = monitor.get_pilot_snapshot()
        assert snapshot.pilot_requests == 0
        assert snapshot.avg_latency_ms == 0.0

    def test_check_alerts_latency(self):
        snapshot = PilotTelemetrySnapshot(
            window_start="", window_end="",
            pilot_requests=10,
            p95_latency_ms=4000,
            error_rate=0.0,
            fallback_rate=0.0,
        )
        monitor = self._make_monitor()
        alerts = monitor.check_alerts(snapshot)
        assert any("latency" in a.lower() for a in alerts)

    def test_check_alerts_error_rate(self):
        snapshot = PilotTelemetrySnapshot(
            window_start="", window_end="",
            pilot_requests=10,
            p95_latency_ms=1000,
            error_rate=0.05,
            fallback_rate=0.0,
        )
        monitor = self._make_monitor()
        alerts = monitor.check_alerts(snapshot)
        assert any("error rate" in a.lower() for a in alerts)

    def test_check_alerts_no_issues(self):
        snapshot = PilotTelemetrySnapshot(
            window_start="", window_end="",
            pilot_requests=10,
            p95_latency_ms=1000,
            error_rate=0.005,
            fallback_rate=0.05,
        )
        monitor = self._make_monitor()
        alerts = monitor.check_alerts(snapshot)
        assert len(alerts) == 0


# ===================================================================
# 6.6.3 – User Feedback Collection
# ===================================================================

class TestFeedbackCollector:
    """Tests for pilot user feedback collection."""

    def test_submit_feedback(self, tmp_path):
        collector = FeedbackCollector(storage_path=str(tmp_path / "feedback.jsonl"))
        fb = collector.submit_feedback(
            user_id=10, session_id=1, rating="positive", comment="Great!"
        )
        assert fb.user_id == 10
        assert fb.rating == "positive"
        assert fb.timestamp != ""

    def test_feedback_persisted_to_file(self, tmp_path):
        path = tmp_path / "feedback.jsonl"
        collector = FeedbackCollector(storage_path=str(path))
        collector.submit_feedback(user_id=10, session_id=1, rating="positive")
        collector.submit_feedback(user_id=20, session_id=2, rating="negative")
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["user_id"] == 10

    def test_feedback_summary(self, tmp_path):
        collector = FeedbackCollector(storage_path=str(tmp_path / "fb.jsonl"))
        collector.submit_feedback(user_id=1, session_id=1, rating="positive")
        collector.submit_feedback(user_id=2, session_id=2, rating="positive")
        collector.submit_feedback(user_id=3, session_id=3, rating="negative")
        summary = collector.get_feedback_summary()
        assert summary["total"] == 3
        assert summary["ratings"]["positive"] == 2
        assert summary["satisfaction_rate"] == pytest.approx(2 / 3)

    def test_feedback_summary_empty(self, tmp_path):
        collector = FeedbackCollector(storage_path=str(tmp_path / "fb.jsonl"))
        summary = collector.get_feedback_summary()
        assert summary["total"] == 0

    def test_feedback_with_category(self, tmp_path):
        collector = FeedbackCollector(storage_path=str(tmp_path / "fb.jsonl"))
        fb = collector.submit_feedback(
            user_id=10, session_id=1, rating="neutral", category="latency"
        )
        assert fb.category == "latency"
        summary = collector.get_feedback_summary()
        assert summary["categories"]["latency"] == 1


# ===================================================================
# 6.6.4 – Bug Identification and Tracking
# ===================================================================

class TestBugTracker:
    """Tests for pilot bug tracking."""

    def test_report_bug(self, tmp_path):
        tracker = BugTracker(storage_path=str(tmp_path / "bugs.jsonl"))
        bug = tracker.report_bug(
            title="Response timeout",
            severity="high",
            user_id=10,
            description="CE runtime timed out after 10s",
        )
        assert bug.id == "PILOT-BUG-0001"
        assert bug.status == "open"
        assert bug.severity == "high"

    def test_report_from_error(self, tmp_path):
        tracker = BugTracker(storage_path=str(tmp_path / "bugs.jsonl"))
        try:
            raise ValueError("test error")
        except ValueError as e:
            bug = tracker.report_from_error(e, user_id=10)
        assert "ValueError" in bug.title
        assert bug.error_type == "ValueError"
        assert bug.error_message == "test error"

    def test_update_status(self, tmp_path):
        tracker = BugTracker(storage_path=str(tmp_path / "bugs.jsonl"))
        bug = tracker.report_bug(title="Bug 1", severity="medium")
        updated = tracker.update_status(bug.id, "fixed", "Patched in v2")
        assert updated.status == "fixed"
        assert updated.resolution == "Patched in v2"

    def test_get_open_bugs(self, tmp_path):
        tracker = BugTracker(storage_path=str(tmp_path / "bugs.jsonl"))
        tracker.report_bug(title="Open bug", severity="high")
        bug2 = tracker.report_bug(title="Fixed bug", severity="low")
        tracker.update_status(bug2.id, "fixed")
        open_bugs = tracker.get_open_bugs()
        assert len(open_bugs) == 1
        assert open_bugs[0].title == "Open bug"

    def test_bug_summary(self, tmp_path):
        tracker = BugTracker(storage_path=str(tmp_path / "bugs.jsonl"))
        tracker.report_bug(title="Bug 1", severity="critical")
        tracker.report_bug(title="Bug 2", severity="high")
        tracker.report_bug(title="Bug 3", severity="high")
        summary = tracker.get_bug_summary()
        assert summary["total"] == 3
        assert summary["by_severity"]["critical"] == 1
        assert summary["by_severity"]["high"] == 2
        assert summary["open_count"] == 3

    def test_bugs_persisted_to_file(self, tmp_path):
        path = tmp_path / "bugs.jsonl"
        tracker = BugTracker(storage_path=str(path))
        tracker.report_bug(title="Bug 1", severity="low")
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["title"] == "Bug 1"

    def test_get_bugs_by_severity(self, tmp_path):
        tracker = BugTracker(storage_path=str(tmp_path / "bugs.jsonl"))
        tracker.report_bug(title="Critical", severity="critical")
        tracker.report_bug(title="Low", severity="low")
        critical = tracker.get_bugs_by_severity("critical")
        assert len(critical) == 1
        assert critical[0].title == "Critical"


# ===================================================================
# 6.6.5 – Quality Iteration Support
# ===================================================================

class TestQualityGate:
    """Tests for quality iteration and threshold checks."""

    def _make_snapshot(self, **overrides):
        defaults = dict(
            window_start="", window_end="",
            total_requests=100, pilot_requests=50, legacy_requests=50,
            avg_latency_ms=500, p95_latency_ms=1500,
            error_count=0, error_rate=0.005,
            fallback_count=2, fallback_rate=0.04,
            avg_context_tokens=200, avg_response_tokens=100,
        )
        defaults.update(overrides)
        return PilotTelemetrySnapshot(**defaults)

    def test_all_checks_pass_healthy_system(self):
        gate = QualityGate()
        snapshot = self._make_snapshot()
        feedback = {"satisfaction_rate": 0.9}
        bugs = {"open_count": 0}
        results = gate.run_checks(snapshot, feedback, bugs)
        assert gate.all_passed(results)
        assert gate.ready_for_expansion(results)

    def test_critical_latency_fails(self):
        gate = QualityGate()
        snapshot = self._make_snapshot(p95_latency_ms=6000)
        results = gate.run_checks(snapshot, {"satisfaction_rate": 0.9}, {"open_count": 0})
        latency_result = next(r for r in results if r.name == "p95_latency_ms")
        assert latency_result.level == "critical"
        assert not latency_result.passed
        assert not gate.all_passed(results)

    def test_warning_level_not_ready_for_expansion(self):
        gate = QualityGate()
        snapshot = self._make_snapshot(error_rate=0.02)  # above target but below critical
        results = gate.run_checks(snapshot, {"satisfaction_rate": 0.9}, {"open_count": 0})
        error_result = next(r for r in results if r.name == "error_rate")
        assert error_result.level == "warning"
        assert not error_result.passed
        assert not gate.ready_for_expansion(results)

    def test_low_satisfaction_detected(self):
        gate = QualityGate()
        snapshot = self._make_snapshot()
        results = gate.run_checks(snapshot, {"satisfaction_rate": 0.4}, {"open_count": 0})
        sat_result = next(r for r in results if r.name == "satisfaction_rate")
        assert sat_result.level == "critical"
        assert not sat_result.passed

    def test_open_bugs_detected(self):
        gate = QualityGate()
        snapshot = self._make_snapshot()
        results = gate.run_checks(snapshot, {"satisfaction_rate": 0.9}, {"open_count": 15})
        bug_result = next(r for r in results if r.name == "open_bug_count")
        assert bug_result.level == "critical"
        assert not bug_result.passed

    def test_custom_thresholds(self):
        custom = [
            QualityThreshold(name="p95_latency_ms", target=2000, warning=1500, critical=4000),
        ]
        gate = QualityGate(thresholds=custom)
        snapshot = self._make_snapshot(p95_latency_ms=2500)
        results = gate.run_checks(snapshot, {}, {})
        assert len(results) == 1
        assert results[0].level == "warning"


# ===================================================================
# Integration: ChatMessageHandler with Pilot Routing
# ===================================================================

class TestHandlerPilotRouting:
    """Tests that ChatMessageHandler routes based on pilot status."""

    def _make_handler(self, user_id, settings_overrides=None, agent=None):
        from app.services.chat_message_handler import ChatMessageHandler
        from app.services.chat_session_service import ChatSessionService

        overrides = settings_overrides or {}
        settings = _make_settings(**overrides)
        session_service = MagicMock(spec=ChatSessionService)
        session_service.get_active_buffer.return_value = []

        registry = PilotUserRegistry(settings)

        return ChatMessageHandler(
            db=MagicMock(),
            session_service=session_service,
            agent=agent,
            user_id=user_id,
            session_id=1,
            settings=settings,
            pilot_registry=registry,
        )

    def test_non_pilot_user_gets_legacy(self):
        handler = self._make_handler(
            user_id=99,
            settings_overrides={
                "PILOT_ROLLOUT_ENABLED": True,
                "PILOT_USER_IDS": "10,20",
            },
        )
        assert handler.runtime == "legacy"

    def test_pilot_user_gets_ce(self):
        agent = MagicMock()
        handler = self._make_handler(
            user_id=10,
            settings_overrides={
                "PILOT_ROLLOUT_ENABLED": True,
                "PILOT_USER_IDS": "10,20",
            },
            agent=agent,
        )
        assert handler.runtime == "ce"

    def test_global_flag_overrides_pilot(self):
        agent = MagicMock()
        handler = self._make_handler(
            user_id=99,
            settings_overrides={
                "USE_CE_CHAT_RUNTIME": True,
                "PILOT_ROLLOUT_ENABLED": False,
            },
            agent=agent,
        )
        assert handler.runtime == "ce"

    def test_pilot_user_without_agent_raises(self):
        with pytest.raises(ValueError, match="ChatAgent is required"):
            self._make_handler(
                user_id=10,
                settings_overrides={
                    "PILOT_ROLLOUT_ENABLED": True,
                    "PILOT_USER_IDS": "10",
                },
                agent=None,
            )
