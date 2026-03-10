"""
Test training plan dataclasses.

This test verifies:
1. Dataclasses can be instantiated correctly
2. Validation logic works for all fields
3. Invalid data raises appropriate errors
"""
import pytest
from datetime import date, datetime
from app.schemas.training_plan import TrainingSession, TrainingWeek, TrainingPlan


def test_training_session_creation():
    """Test creating a valid training session."""
    session = TrainingSession(
        day_of_week=1,
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy",
        description="Easy pace, focus on form"
    )
    
    assert session.day_of_week == 1
    assert session.session_type == "easy_run"
    assert session.duration_minutes == 45
    assert session.intensity == "easy"
    assert session.description == "Easy pace, focus on form"
    assert session.completed is False
    assert session.matched_activity_id is None
    assert session.validate() is True


def test_training_session_invalid_day_of_week():
    """Test that invalid day_of_week raises error."""
    session = TrainingSession(
        day_of_week=8,  # Invalid
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy",
        description="Test"
    )
    
    with pytest.raises(ValueError, match="day_of_week must be between 1 and 7"):
        session.validate()


def test_training_session_invalid_session_type():
    """Test that invalid session_type raises error."""
    session = TrainingSession(
        day_of_week=1,
        session_type="invalid_type",  # Invalid
        duration_minutes=45,
        intensity="easy",
        description="Test"
    )
    
    with pytest.raises(ValueError, match="Invalid session_type"):
        session.validate()


def test_training_session_invalid_duration():
    """Test that negative duration raises error."""
    session = TrainingSession(
        day_of_week=1,
        session_type="easy_run",
        duration_minutes=-10,  # Invalid
        intensity="easy",
        description="Test"
    )
    
    with pytest.raises(ValueError, match="duration_minutes must be >= 0"):
        session.validate()


def test_training_session_invalid_intensity():
    """Test that invalid intensity raises error."""
    session = TrainingSession(
        day_of_week=1,
        session_type="easy_run",
        duration_minutes=45,
        intensity="super_hard",  # Invalid
        description="Test"
    )
    
    with pytest.raises(ValueError, match="Invalid intensity"):
        session.validate()


def test_training_week_creation():
    """Test creating a valid training week."""
    sessions = [
        TrainingSession(
            day_of_week=1,
            session_type="easy_run",
            duration_minutes=45,
            intensity="easy",
            description="Easy run"
        ),
        TrainingSession(
            day_of_week=3,
            session_type="interval",
            duration_minutes=60,
            intensity="hard",
            description="Interval training"
        )
    ]
    
    week = TrainingWeek(
        week_number=1,
        focus="Base building",
        volume_target=5.0,
        sessions=sessions
    )
    
    assert week.week_number == 1
    assert week.focus == "Base building"
    assert week.volume_target == 5.0
    assert len(week.sessions) == 2
    assert week.validate() is True


def test_training_week_invalid_week_number():
    """Test that invalid week_number raises error."""
    week = TrainingWeek(
        week_number=0,  # Invalid
        focus="Test",
        volume_target=5.0
    )
    
    with pytest.raises(ValueError, match="week_number must be >= 1"):
        week.validate()


def test_training_week_invalid_volume_target():
    """Test that negative volume_target raises error."""
    week = TrainingWeek(
        week_number=1,
        focus="Test",
        volume_target=-5.0  # Invalid
    )
    
    with pytest.raises(ValueError, match="volume_target must be >= 0"):
        week.validate()


def test_training_week_invalid_session():
    """Test that invalid session in week raises error."""
    sessions = [
        TrainingSession(
            day_of_week=8,  # Invalid
            session_type="easy_run",
            duration_minutes=45,
            intensity="easy",
            description="Test"
        )
    ]
    
    week = TrainingWeek(
        week_number=1,
        focus="Test",
        volume_target=5.0,
        sessions=sessions
    )
    
    with pytest.raises(ValueError, match="Session validation failed"):
        week.validate()


def test_training_plan_creation():
    """Test creating a valid training plan."""
    sessions = [
        TrainingSession(
            day_of_week=1,
            session_type="easy_run",
            duration_minutes=45,
            intensity="easy",
            description="Easy run"
        )
    ]
    
    weeks = [
        TrainingWeek(
            week_number=1,
            focus="Base building",
            volume_target=5.0,
            sessions=sessions
        )
    ]
    
    plan = TrainingPlan(
        user_id=1,
        title="Marathon Training",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active",
        weeks=weeks
    )
    
    assert plan.user_id == 1
    assert plan.title == "Marathon Training"
    assert plan.sport == "running"
    assert plan.start_date == date(2024, 1, 1)
    assert plan.end_date == date(2024, 4, 1)
    assert plan.status == "active"
    assert len(plan.weeks) == 1
    assert plan.id is None
    assert plan.goal_id is None
    assert plan.validate() is True


def test_training_plan_invalid_status():
    """Test that invalid status raises error."""
    plan = TrainingPlan(
        user_id=1,
        title="Test Plan",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="invalid_status"  # Invalid
    )
    
    with pytest.raises(ValueError, match="Invalid status"):
        plan.validate()


def test_training_plan_invalid_dates():
    """Test that start_date >= end_date raises error."""
    plan = TrainingPlan(
        user_id=1,
        title="Test Plan",
        sport="running",
        start_date=date(2024, 4, 1),
        end_date=date(2024, 1, 1),  # Before start_date
        status="active"
    )
    
    with pytest.raises(ValueError, match="start_date must be before end_date"):
        plan.validate()


def test_training_plan_invalid_sport():
    """Test that invalid sport raises error."""
    plan = TrainingPlan(
        user_id=1,
        title="Test Plan",
        sport="invalid_sport",  # Invalid
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active"
    )
    
    with pytest.raises(ValueError, match="Invalid sport"):
        plan.validate()


def test_training_plan_empty_title():
    """Test that empty title raises error."""
    plan = TrainingPlan(
        user_id=1,
        title="   ",  # Empty after strip
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active"
    )
    
    with pytest.raises(ValueError, match="title cannot be empty"):
        plan.validate()


def test_training_plan_invalid_week():
    """Test that invalid week in plan raises error."""
    weeks = [
        TrainingWeek(
            week_number=0,  # Invalid
            focus="Test",
            volume_target=5.0
        )
    ]
    
    plan = TrainingPlan(
        user_id=1,
        title="Test Plan",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active",
        weeks=weeks
    )
    
    with pytest.raises(ValueError, match="Week 0 validation failed"):
        plan.validate()


def test_all_session_types():
    """Test that all valid session types are accepted."""
    valid_session_types = [
        'easy_run', 'tempo_run', 'interval', 'long_run', 'recovery_run',
        'easy_ride', 'tempo_ride', 'interval_ride', 'long_ride',
        'swim_technique', 'swim_endurance', 'swim_interval',
        'rest', 'cross_training', 'strength'
    ]
    
    for session_type in valid_session_types:
        session = TrainingSession(
            day_of_week=1,
            session_type=session_type,
            duration_minutes=45,
            intensity="easy",
            description="Test"
        )
        assert session.validate() is True


def test_all_intensities():
    """Test that all valid intensities are accepted."""
    valid_intensities = ['recovery', 'easy', 'moderate', 'hard', 'max']
    
    for intensity in valid_intensities:
        session = TrainingSession(
            day_of_week=1,
            session_type="easy_run",
            duration_minutes=45,
            intensity=intensity,
            description="Test"
        )
        assert session.validate() is True


def test_all_sports():
    """Test that all valid sports are accepted."""
    valid_sports = ['running', 'cycling', 'swimming', 'triathlon', 'other']
    
    for sport in valid_sports:
        plan = TrainingPlan(
            user_id=1,
            title="Test Plan",
            sport=sport,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 4, 1),
            status="active"
        )
        assert plan.validate() is True


def test_all_statuses():
    """Test that all valid statuses are accepted."""
    valid_statuses = ['draft', 'active', 'completed', 'abandoned']
    
    for status in valid_statuses:
        plan = TrainingPlan(
            user_id=1,
            title="Test Plan",
            sport="running",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 4, 1),
            status=status
        )
        assert plan.validate() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
