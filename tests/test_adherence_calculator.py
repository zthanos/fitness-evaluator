"""Tests for Adherence Calculator Service

Tests adherence score calculations at multiple levels.
Includes unit tests and property-based tests.
"""
import pytest
from datetime import date, timedelta
from hypothesis import given, strategies as st
from hypothesis.strategies import composite
from app.services.adherence_calculator import AdherenceCalculator
from app.models.training_plan import TrainingPlan
from app.models.training_plan_week import TrainingPlanWeek
from app.models.training_plan_session import TrainingPlanSession


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_session_completed():
    """Create a completed training session."""
    return TrainingPlanSession(
        id='session-1',
        week_id='week-1',
        day_of_week=1,
        session_type='easy_run',
        duration_minutes=45,
        intensity='easy',
        description='Easy recovery run',
        completed=True,
        matched_activity_id='activity-1'
    )


@pytest.fixture
def sample_session_incomplete():
    """Create an incomplete training session."""
    return TrainingPlanSession(
        id='session-2',
        week_id='week-1',
        day_of_week=2,
        session_type='tempo_run',
        duration_minutes=60,
        intensity='moderate',
        description='Tempo run',
        completed=False,
        matched_activity_id=None
    )


@pytest.fixture
def sample_week_full_adherence():
    """Create a week with 100% adherence (all sessions completed)."""
    week = TrainingPlanWeek(
        id='week-1',
        plan_id='plan-1',
        week_number=1,
        focus='Base building',
        volume_target=5.0
    )
    week.sessions = [
        TrainingPlanSession(
            id=f'session-{i}',
            week_id='week-1',
            day_of_week=i,
            session_type='easy_run',
            duration_minutes=45,
            intensity='easy',
            completed=True
        )
        for i in range(1, 4)  # 3 sessions, all completed
    ]
    return week


@pytest.fixture
def sample_week_partial_adherence():
    """Create a week with partial adherence (some sessions completed)."""
    week = TrainingPlanWeek(
        id='week-2',
        plan_id='plan-1',
        week_number=2,
        focus='Building intensity',
        volume_target=6.0
    )
    week.sessions = [
        TrainingPlanSession(
            id='session-4',
            week_id='week-2',
            day_of_week=1,
            session_type='easy_run',
            duration_minutes=45,
            intensity='easy',
            completed=True
        ),
        TrainingPlanSession(
            id='session-5',
            week_id='week-2',
            day_of_week=3,
            session_type='tempo_run',
            duration_minutes=60,
            intensity='moderate',
            completed=False
        ),
        TrainingPlanSession(
            id='session-6',
            week_id='week-2',
            day_of_week=5,
            session_type='long_run',
            duration_minutes=90,
            intensity='easy',
            completed=True
        )
    ]
    return week


@pytest.fixture
def sample_plan():
    """Create a sample training plan with multiple weeks."""
    plan = TrainingPlan(
        id='plan-1',
        user_id=1,
        title='Marathon Training',
        sport='running',
        goal_id='goal-1',
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status='active'
    )
    
    # Week 1: 100% adherence (3/3 completed)
    week1 = TrainingPlanWeek(
        id='week-1',
        plan_id='plan-1',
        week_number=1,
        focus='Base building',
        volume_target=5.0
    )
    week1.sessions = [
        TrainingPlanSession(
            id=f'session-1-{i}',
            week_id='week-1',
            day_of_week=i,
            session_type='easy_run',
            duration_minutes=45,
            intensity='easy',
            completed=True
        )
        for i in range(1, 4)
    ]
    
    # Week 2: 66.67% adherence (2/3 completed)
    week2 = TrainingPlanWeek(
        id='week-2',
        plan_id='plan-1',
        week_number=2,
        focus='Building intensity',
        volume_target=6.0
    )
    week2.sessions = [
        TrainingPlanSession(
            id='session-2-1',
            week_id='week-2',
            day_of_week=1,
            session_type='easy_run',
            duration_minutes=45,
            intensity='easy',
            completed=True
        ),
        TrainingPlanSession(
            id='session-2-2',
            week_id='week-2',
            day_of_week=3,
            session_type='tempo_run',
            duration_minutes=60,
            intensity='moderate',
            completed=False
        ),
        TrainingPlanSession(
            id='session-2-3',
            week_id='week-2',
            day_of_week=5,
            session_type='long_run',
            duration_minutes=90,
            intensity='easy',
            completed=True
        )
    ]
    
    plan.weeks = [week1, week2]
    return plan


# ============================================================================
# Unit Tests - Session Adherence
# ============================================================================

def test_calculate_session_adherence_completed(sample_session_completed):
    """Test session adherence for completed session."""
    adherence = AdherenceCalculator.calculate_session_adherence(sample_session_completed)
    assert adherence == 100.0


def test_calculate_session_adherence_incomplete(sample_session_incomplete):
    """Test session adherence for incomplete session."""
    adherence = AdherenceCalculator.calculate_session_adherence(sample_session_incomplete)
    assert adherence == 0.0


# ============================================================================
# Unit Tests - Week Adherence
# ============================================================================

def test_calculate_week_adherence_full(sample_week_full_adherence):
    """Test week adherence with 100% completion."""
    adherence = AdherenceCalculator.calculate_week_adherence(sample_week_full_adherence)
    assert adherence == 100.0


def test_calculate_week_adherence_partial(sample_week_partial_adherence):
    """Test week adherence with partial completion."""
    adherence = AdherenceCalculator.calculate_week_adherence(sample_week_partial_adherence)
    # 2 out of 3 sessions completed = 66.67%
    assert abs(adherence - 66.67) < 0.1


def test_calculate_week_adherence_empty():
    """Test week adherence with no sessions."""
    week = TrainingPlanWeek(
        id='week-empty',
        plan_id='plan-1',
        week_number=1,
        focus='Empty week'
    )
    week.sessions = []
    
    adherence = AdherenceCalculator.calculate_week_adherence(week)
    assert adherence == 0.0


def test_calculate_week_adherence_zero():
    """Test week adherence with no completed sessions."""
    week = TrainingPlanWeek(
        id='week-zero',
        plan_id='plan-1',
        week_number=1,
        focus='No completion'
    )
    week.sessions = [
        TrainingPlanSession(
            id=f'session-{i}',
            week_id='week-zero',
            day_of_week=i,
            session_type='easy_run',
            duration_minutes=45,
            intensity='easy',
            completed=False
        )
        for i in range(1, 4)
    ]
    
    adherence = AdherenceCalculator.calculate_week_adherence(week)
    assert adherence == 0.0


# ============================================================================
# Unit Tests - Plan Adherence
# ============================================================================

def test_calculate_plan_adherence(sample_plan):
    """Test overall plan adherence calculation."""
    adherence = AdherenceCalculator.calculate_plan_adherence(sample_plan)
    # Week 1: 3/3 completed, Week 2: 2/3 completed
    # Total: 5/6 = 83.33%
    assert abs(adherence - 83.33) < 0.1


def test_calculate_plan_adherence_empty():
    """Test plan adherence with no weeks."""
    plan = TrainingPlan(
        id='plan-empty',
        user_id=1,
        title='Empty Plan',
        sport='running',
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        status='draft'
    )
    plan.weeks = []
    
    adherence = AdherenceCalculator.calculate_plan_adherence(plan)
    assert adherence == 0.0


def test_calculate_plan_adherence_full():
    """Test plan adherence with 100% completion."""
    plan = TrainingPlan(
        id='plan-full',
        user_id=1,
        title='Completed Plan',
        sport='running',
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        status='completed'
    )
    
    week = TrainingPlanWeek(
        id='week-1',
        plan_id='plan-full',
        week_number=1,
        focus='All done'
    )
    week.sessions = [
        TrainingPlanSession(
            id=f'session-{i}',
            week_id='week-1',
            day_of_week=i,
            session_type='easy_run',
            duration_minutes=45,
            intensity='easy',
            completed=True
        )
        for i in range(1, 8)  # All 7 days completed
    ]
    
    plan.weeks = [week]
    adherence = AdherenceCalculator.calculate_plan_adherence(plan)
    assert adherence == 100.0


# ============================================================================
# Unit Tests - Time Series
# ============================================================================

def test_get_adherence_time_series(sample_plan):
    """Test adherence time series generation."""
    time_series = AdherenceCalculator.get_adherence_time_series(sample_plan)
    
    assert len(time_series) == 2
    assert time_series[0]['week'] == 1
    assert time_series[0]['adherence'] == 100.0
    assert time_series[1]['week'] == 2
    assert abs(time_series[1]['adherence'] - 66.67) < 0.1


def test_get_adherence_time_series_empty():
    """Test time series with empty plan."""
    plan = TrainingPlan(
        id='plan-empty',
        user_id=1,
        title='Empty Plan',
        sport='running',
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        status='draft'
    )
    plan.weeks = []
    
    time_series = AdherenceCalculator.get_adherence_time_series(plan)
    assert time_series == []


# ============================================================================
# Unit Tests - Adherence Summary
# ============================================================================

def test_get_adherence_summary(sample_plan):
    """Test comprehensive adherence summary."""
    summary = AdherenceCalculator.get_adherence_summary(sample_plan)
    
    assert 'overall_adherence' in summary
    assert 'adherence_by_week' in summary
    assert 'total_sessions' in summary
    assert 'completed_sessions' in summary
    assert 'pending_sessions' in summary
    
    assert abs(summary['overall_adherence'] - 83.33) < 0.1
    assert summary['total_sessions'] == 6
    assert summary['completed_sessions'] == 5
    assert summary['pending_sessions'] == 1
    assert len(summary['adherence_by_week']) == 2


# ============================================================================
# Property-Based Tests
# ============================================================================

@composite
def training_session_strategy(draw):
    """Generate random training sessions."""
    completed = draw(st.booleans())
    return TrainingPlanSession(
        id=f'session-{draw(st.integers(min_value=1, max_value=10000))}',
        week_id='week-test',
        day_of_week=draw(st.integers(min_value=1, max_value=7)),
        session_type=draw(st.sampled_from(['easy_run', 'tempo_run', 'interval', 'long_run', 'rest'])),
        duration_minutes=draw(st.integers(min_value=0, max_value=180)),
        intensity=draw(st.sampled_from(['recovery', 'easy', 'moderate', 'hard'])),
        completed=completed
    )


@composite
def training_week_strategy(draw):
    """Generate random training weeks with sessions."""
    num_sessions = draw(st.integers(min_value=0, max_value=10))
    week = TrainingPlanWeek(
        id=f'week-{draw(st.integers(min_value=1, max_value=100))}',
        plan_id='plan-test',
        week_number=draw(st.integers(min_value=1, max_value=52)),
        focus='Test focus'
    )
    week.sessions = [draw(training_session_strategy()) for _ in range(num_sessions)]
    return week


@composite
def training_plan_strategy(draw):
    """Generate random training plans with weeks."""
    num_weeks = draw(st.integers(min_value=0, max_value=20))
    plan = TrainingPlan(
        id='plan-test',
        user_id=1,
        title='Test Plan',
        sport='running',
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        status='active'
    )
    plan.weeks = [draw(training_week_strategy()) for _ in range(num_weeks)]
    return plan


@given(session=training_session_strategy())
def test_property_session_adherence_binary(session):
    """
    Property: Session adherence is always either 0% or 100%.
    
    **Validates: Requirements 15.1**
    """
    adherence = AdherenceCalculator.calculate_session_adherence(session)
    assert adherence in [0.0, 100.0], f"Session adherence must be 0 or 100, got {adherence}"


@given(session=training_session_strategy())
def test_property_session_adherence_matches_completed(session):
    """
    Property: Session adherence is 100% iff completed is True.
    
    **Validates: Requirements 15.1**
    """
    adherence = AdherenceCalculator.calculate_session_adherence(session)
    if session.completed:
        assert adherence == 100.0
    else:
        assert adherence == 0.0


@given(week=training_week_strategy())
def test_property_week_adherence_range(week):
    """
    Property: Week adherence is always between 0% and 100%.
    
    **Validates: Requirements 15.2**
    """
    adherence = AdherenceCalculator.calculate_week_adherence(week)
    assert 0.0 <= adherence <= 100.0, f"Week adherence must be in [0, 100], got {adherence}"


@given(week=training_week_strategy())
def test_property_week_adherence_calculation(week):
    """
    Property: Week adherence equals (completed_count / total_count) * 100.
    
    **Validates: Requirements 15.2**
    """
    if not week.sessions:
        expected = 0.0
    else:
        completed = sum(1 for s in week.sessions if s.completed)
        total = len(week.sessions)
        expected = (completed / total) * 100.0
    
    adherence = AdherenceCalculator.calculate_week_adherence(week)
    assert abs(adherence - expected) < 0.01, f"Expected {expected}, got {adherence}"


@given(plan=training_plan_strategy())
def test_property_plan_adherence_range(plan):
    """
    Property: Plan adherence is always between 0% and 100%.
    
    **Validates: Requirements 15.3**
    """
    adherence = AdherenceCalculator.calculate_plan_adherence(plan)
    assert 0.0 <= adherence <= 100.0, f"Plan adherence must be in [0, 100], got {adherence}"


@given(plan=training_plan_strategy())
def test_property_plan_adherence_calculation(plan):
    """
    Property: Plan adherence equals (total_completed / total_sessions) * 100.
    
    **Validates: Requirements 15.3**
    """
    total_sessions = sum(len(week.sessions) for week in plan.weeks)
    
    if total_sessions == 0:
        expected = 0.0
    else:
        completed_sessions = sum(
            sum(1 for s in week.sessions if s.completed)
            for week in plan.weeks
        )
        expected = (completed_sessions / total_sessions) * 100.0
    
    adherence = AdherenceCalculator.calculate_plan_adherence(plan)
    assert abs(adherence - expected) < 0.01, f"Expected {expected}, got {adherence}"


@given(plan=training_plan_strategy())
def test_property_time_series_length(plan):
    """
    Property: Time series length equals number of weeks in plan.
    """
    time_series = AdherenceCalculator.get_adherence_time_series(plan)
    assert len(time_series) == len(plan.weeks)


@given(plan=training_plan_strategy())
def test_property_time_series_week_numbers(plan):
    """
    Property: Time series contains correct week numbers.
    """
    time_series = AdherenceCalculator.get_adherence_time_series(plan)
    
    for i, entry in enumerate(time_series):
        assert entry['week'] == plan.weeks[i].week_number


@given(plan=training_plan_strategy())
def test_property_summary_consistency(plan):
    """
    Property: Summary metrics are internally consistent.
    """
    summary = AdherenceCalculator.get_adherence_summary(plan)
    
    # Total sessions = completed + pending
    assert summary['total_sessions'] == summary['completed_sessions'] + summary['pending_sessions']
    
    # Adherence matches calculation
    if summary['total_sessions'] > 0:
        expected_adherence = (summary['completed_sessions'] / summary['total_sessions']) * 100.0
        assert abs(summary['overall_adherence'] - expected_adherence) < 0.01
    else:
        assert summary['overall_adherence'] == 0.0
    
    # Time series length matches weeks
    assert len(summary['adherence_by_week']) == len(plan.weeks)
