"""Tests for Session Matcher Service

Tests automatic matching of Strava activities to planned training sessions.
"""
import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.services.session_matcher import SessionMatcher
from app.models.strava_activity import StravaActivity
from app.models.training_plan import TrainingPlan
from app.models.training_plan_week import TrainingPlanWeek
from app.models.training_plan_session import TrainingPlanSession
from app.models.athlete import Athlete


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create test athlete
    athlete = Athlete(id=1, name="Test Athlete", email="test@example.com")
    session.add(athlete)
    session.commit()
    
    yield session
    session.close()


@pytest.fixture
def session_matcher(db_session):
    """Create SessionMatcher instance."""
    return SessionMatcher(db_session)


@pytest.fixture
def active_training_plan(db_session):
    """Create an active training plan with sessions."""
    plan = TrainingPlan(
        user_id=1,
        title="Test Marathon Plan",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active"
    )
    db_session.add(plan)
    db_session.flush()
    
    # Add week 1
    week1 = TrainingPlanWeek(
        plan_id=plan.id,
        week_number=1,
        focus="Base building",
        volume_target=10.0
    )
    db_session.add(week1)
    db_session.flush()
    
    # Add sessions for week 1
    # Monday - Easy run
    session1 = TrainingPlanSession(
        week_id=week1.id,
        day_of_week=1,  # Monday
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy",
        description="Easy pace run"
    )
    db_session.add(session1)
    
    # Wednesday - Tempo run
    session2 = TrainingPlanSession(
        week_id=week1.id,
        day_of_week=3,  # Wednesday
        session_type="tempo_run",
        duration_minutes=60,
        intensity="moderate",
        description="Tempo pace"
    )
    db_session.add(session2)
    
    # Friday - Interval run
    session3 = TrainingPlanSession(
        week_id=week1.id,
        day_of_week=5,  # Friday
        session_type="interval",
        duration_minutes=50,
        intensity="hard",
        description="5x1000m intervals"
    )
    db_session.add(session3)
    
    db_session.commit()
    return plan


@pytest.fixture
def strava_activity(db_session):
    """Create a Strava activity."""
    activity = StravaActivity(
        athlete_id=1,
        strava_id=123456,
        activity_type="Run",
        start_date=datetime(2024, 1, 1, 12, 30, 0),  # Monday 12:30pm (close to scheduled noon)
        moving_time_s=2700,  # 45 minutes
        distance_m=7500,
        avg_hr=130,  # Easy intensity (matches easy session)
        max_hr=180,
        raw_json="{}"
    )
    db_session.add(activity)
    db_session.commit()
    return activity


class TestFindCandidateSessions:
    """Test finding candidate sessions for matching."""
    
    def test_finds_sessions_within_24_hours(self, session_matcher, active_training_plan, strava_activity, db_session):
        """Should find sessions within 24 hours of activity."""
        candidates = session_matcher.find_candidate_sessions(strava_activity, user_id=1)
        
        # Should find the Monday easy run (same day)
        assert len(candidates) > 0
        assert any(s.session_type == "easy_run" for s in candidates)
    
    def test_filters_by_user_id(self, session_matcher, active_training_plan, strava_activity, db_session):
        """Should only return sessions for the specified user."""
        # Create plan for different user
        other_plan = TrainingPlan(
            user_id=2,
            title="Other Plan",
            sport="running",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
            status="active"
        )
        db_session.add(other_plan)
        db_session.flush()
        
        week = TrainingPlanWeek(
            plan_id=other_plan.id,
            week_number=1,
            focus="Test"
        )
        db_session.add(week)
        db_session.flush()
        
        session = TrainingPlanSession(
            week_id=week.id,
            day_of_week=1,
            session_type="easy_run",
            duration_minutes=45,
            intensity="easy"
        )
        db_session.add(session)
        db_session.commit()
        
        # Query for user 1
        candidates = session_matcher.find_candidate_sessions(strava_activity, user_id=1)
        
        # Should not include user 2's sessions
        for candidate in candidates:
            assert candidate.week.plan.user_id == 1
    
    def test_filters_by_active_status(self, session_matcher, strava_activity, db_session):
        """Should only return sessions from active plans."""
        # Create draft plan
        draft_plan = TrainingPlan(
            user_id=1,
            title="Draft Plan",
            sport="running",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
            status="draft"
        )
        db_session.add(draft_plan)
        db_session.flush()
        
        week = TrainingPlanWeek(
            plan_id=draft_plan.id,
            week_number=1,
            focus="Test"
        )
        db_session.add(week)
        db_session.flush()
        
        session = TrainingPlanSession(
            week_id=week.id,
            day_of_week=1,
            session_type="easy_run",
            duration_minutes=45,
            intensity="easy"
        )
        db_session.add(session)
        db_session.commit()
        
        candidates = session_matcher.find_candidate_sessions(strava_activity, user_id=1)
        
        # Should not include draft plan sessions
        for candidate in candidates:
            assert candidate.week.plan.status == "active"
    
    def test_excludes_completed_sessions(self, session_matcher, active_training_plan, strava_activity, db_session):
        """Should not return already completed sessions."""
        # Mark Monday session as completed
        session = (
            db_session.query(TrainingPlanSession)
            .join(TrainingPlanWeek)
            .filter(
                TrainingPlanWeek.plan_id == active_training_plan.id,
                TrainingPlanSession.day_of_week == 1
            )
            .first()
        )
        session.completed = True
        db_session.commit()
        
        candidates = session_matcher.find_candidate_sessions(strava_activity, user_id=1)
        
        # Should not include completed session
        assert all(not c.completed for c in candidates)
    
    def test_excludes_already_matched_sessions(self, session_matcher, active_training_plan, strava_activity, db_session):
        """Should not return sessions already matched to activities."""
        # Mark Monday session as matched
        session = (
            db_session.query(TrainingPlanSession)
            .join(TrainingPlanWeek)
            .filter(
                TrainingPlanWeek.plan_id == active_training_plan.id,
                TrainingPlanSession.day_of_week == 1
            )
            .first()
        )
        session.matched_activity_id = "some-activity-id"
        db_session.commit()
        
        candidates = session_matcher.find_candidate_sessions(strava_activity, user_id=1)
        
        # Should not include matched session
        assert all(c.matched_activity_id is None for c in candidates)


class TestCalculateMatchConfidence:
    """Test confidence score calculation."""
    
    def test_perfect_match_scores_high(self, session_matcher, active_training_plan, db_session):
        """Perfect match should score close to 100."""
        # Get Monday session
        session = (
            db_session.query(TrainingPlanSession)
            .join(TrainingPlanWeek)
            .filter(
                TrainingPlanWeek.plan_id == active_training_plan.id,
                TrainingPlanSession.day_of_week == 1
            )
            .first()
        )
        
        # Create activity matching the session perfectly
        activity = StravaActivity(
            athlete_id=1,
            strava_id=123456,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 12, 0, 0),  # Monday noon (scheduled time)
            moving_time_s=2700,  # 45 minutes (exact match)
            distance_m=7500,
            avg_hr=130,  # Easy intensity
            max_hr=180,
            raw_json="{}"
        )
        
        confidence = session_matcher.calculate_match_confidence(activity, session)
        
        # Should score very high (time + sport + duration + intensity)
        assert confidence >= 90
    
    def test_time_proximity_scoring(self, session_matcher, active_training_plan, db_session):
        """Test time proximity score calculation."""
        session = (
            db_session.query(TrainingPlanSession)
            .join(TrainingPlanWeek)
            .filter(
                TrainingPlanWeek.plan_id == active_training_plan.id,
                TrainingPlanSession.day_of_week == 1
            )
            .first()
        )
        
        # Within 2 hours: 40 points
        activity_2h = StravaActivity(
            athlete_id=1,
            strava_id=1,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 13, 0, 0),  # 1 hour after scheduled
            moving_time_s=2700,
            raw_json="{}"
        )
        confidence_2h = session_matcher.calculate_match_confidence(activity_2h, session)
        
        # Within 12 hours: 30 points
        activity_12h = StravaActivity(
            athlete_id=1,
            strava_id=2,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 20, 0, 0),  # 8 hours after scheduled
            moving_time_s=2700,
            raw_json="{}"
        )
        confidence_12h = session_matcher.calculate_match_confidence(activity_12h, session)
        
        # Within 24 hours: 20 points
        activity_24h = StravaActivity(
            athlete_id=1,
            strava_id=3,
            activity_type="Run",
            start_date=datetime(2024, 1, 2, 10, 0, 0),  # 22 hours after scheduled
            moving_time_s=2700,
            raw_json="{}"
        )
        confidence_24h = session_matcher.calculate_match_confidence(activity_24h, session)
        
        # Confidence should decrease with time distance
        assert confidence_2h > confidence_12h > confidence_24h
    
    def test_sport_type_matching(self, session_matcher, active_training_plan, db_session):
        """Test sport type match scoring."""
        session = (
            db_session.query(TrainingPlanSession)
            .join(TrainingPlanWeek)
            .filter(
                TrainingPlanWeek.plan_id == active_training_plan.id,
                TrainingPlanSession.day_of_week == 1
            )
            .first()
        )
        
        # Matching sport type
        activity_match = StravaActivity(
            athlete_id=1,
            strava_id=1,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 12, 0, 0),
            moving_time_s=2700,
            raw_json="{}"
        )
        confidence_match = session_matcher.calculate_match_confidence(activity_match, session)
        
        # Non-matching sport type
        activity_no_match = StravaActivity(
            athlete_id=1,
            strava_id=2,
            activity_type="Ride",
            start_date=datetime(2024, 1, 1, 12, 0, 0),
            moving_time_s=2700,
            raw_json="{}"
        )
        confidence_no_match = session_matcher.calculate_match_confidence(activity_no_match, session)
        
        # Matching sport should score 30 points higher
        assert confidence_match - confidence_no_match == 30
    
    def test_duration_similarity_scoring(self, session_matcher, active_training_plan, db_session):
        """Test duration similarity scoring."""
        session = (
            db_session.query(TrainingPlanSession)
            .join(TrainingPlanWeek)
            .filter(
                TrainingPlanWeek.plan_id == active_training_plan.id,
                TrainingPlanSession.day_of_week == 1
            )
            .first()
        )
        # Session is 45 minutes
        
        # Within ±20%: 20 points (36-54 minutes)
        activity_close = StravaActivity(
            athlete_id=1,
            strava_id=1,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 12, 0, 0),
            moving_time_s=2700,  # 45 minutes (exact)
            raw_json="{}"
        )
        confidence_close = session_matcher.calculate_match_confidence(activity_close, session)
        
        # Within ±40%: 10 points (27-63 minutes)
        activity_medium = StravaActivity(
            athlete_id=1,
            strava_id=2,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 12, 0, 0),
            moving_time_s=3600,  # 60 minutes (33% over)
            raw_json="{}"
        )
        confidence_medium = session_matcher.calculate_match_confidence(activity_medium, session)
        
        # Outside ±40%: 0 points
        activity_far = StravaActivity(
            athlete_id=1,
            strava_id=3,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 12, 0, 0),
            moving_time_s=5400,  # 90 minutes (100% over)
            raw_json="{}"
        )
        confidence_far = session_matcher.calculate_match_confidence(activity_far, session)
        
        # Closer duration should score higher
        assert confidence_close > confidence_medium > confidence_far


class TestMatchActivity:
    """Test complete activity matching flow."""
    
    def test_matches_activity_above_threshold(self, session_matcher, active_training_plan, strava_activity, db_session):
        """Should match activity when confidence > 80%."""
        matched_session_id = session_matcher.match_activity(strava_activity, user_id=1)
        
        # Should return matched session ID
        assert matched_session_id is not None
        
        # Verify session was updated
        session = db_session.query(TrainingPlanSession).filter_by(id=matched_session_id).first()
        assert session.completed is True
        assert session.matched_activity_id == strava_activity.id
    
    def test_does_not_match_below_threshold(self, session_matcher, active_training_plan, db_session):
        """Should not match when confidence <= 80%."""
        # Create activity that doesn't match well (wrong sport, wrong time)
        activity = StravaActivity(
            athlete_id=1,
            strava_id=999,
            activity_type="Swim",  # Wrong sport
            start_date=datetime(2024, 1, 5, 8, 0, 0),  # Wrong day
            moving_time_s=1800,  # Wrong duration
            raw_json="{}"
        )
        db_session.add(activity)
        db_session.commit()
        
        matched_session_id = session_matcher.match_activity(activity, user_id=1)
        
        # Should not match
        assert matched_session_id is None
    
    def test_selects_best_match_when_multiple_candidates(self, session_matcher, active_training_plan, db_session):
        """Should select the best matching session when multiple candidates exist."""
        # Create activity on Wednesday that could match both Wednesday and Friday sessions
        activity = StravaActivity(
            athlete_id=1,
            strava_id=789,
            activity_type="Run",
            start_date=datetime(2024, 1, 3, 12, 0, 0),  # Wednesday
            moving_time_s=3600,  # 60 minutes (matches Wednesday tempo run)
            avg_hr=150,  # Moderate intensity
            max_hr=180,
            raw_json="{}"
        )
        db_session.add(activity)
        db_session.commit()
        
        matched_session_id = session_matcher.match_activity(activity, user_id=1)
        
        # Should match Wednesday tempo run (better time and duration match)
        session = db_session.query(TrainingPlanSession).filter_by(id=matched_session_id).first()
        assert session.day_of_week == 3  # Wednesday
        assert session.session_type == "tempo_run"
    
    def test_does_not_match_same_session_twice(self, session_matcher, active_training_plan, db_session):
        """Should not match a session that's already matched."""
        # First activity
        activity1 = StravaActivity(
            athlete_id=1,
            strava_id=111,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 8, 0, 0),
            moving_time_s=2700,
            raw_json="{}"
        )
        db_session.add(activity1)
        db_session.commit()
        
        # Match first activity
        matched_id_1 = session_matcher.match_activity(activity1, user_id=1)
        assert matched_id_1 is not None
        
        # Second activity (similar to first)
        activity2 = StravaActivity(
            athlete_id=1,
            strava_id=222,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, 18, 0, 0),  # Same day, different time
            moving_time_s=2700,
            raw_json="{}"
        )
        db_session.add(activity2)
        db_session.commit()
        
        # Try to match second activity
        matched_id_2 = session_matcher.match_activity(activity2, user_id=1)
        
        # Should either not match or match a different session
        if matched_id_2:
            assert matched_id_2 != matched_id_1
    
    def test_handles_no_candidates_gracefully(self, session_matcher, db_session):
        """Should handle case when no candidate sessions exist."""
        # Create activity with no matching plan
        activity = StravaActivity(
            athlete_id=1,
            strava_id=999,
            activity_type="Run",
            start_date=datetime(2025, 1, 1, 8, 0, 0),  # Far future
            moving_time_s=2700,
            raw_json="{}"
        )
        db_session.add(activity)
        db_session.commit()
        
        matched_session_id = session_matcher.match_activity(activity, user_id=1)
        
        # Should return None without error
        assert matched_session_id is None
    
    def test_performance_within_5_seconds(self, session_matcher, active_training_plan, strava_activity, db_session):
        """Should complete matching within 5 seconds."""
        import time
        
        start_time = time.time()
        session_matcher.match_activity(strava_activity, user_id=1)
        elapsed_time = time.time() - start_time
        
        # Should complete within 5 seconds
        assert elapsed_time < 5.0
    
    def test_triggers_adherence_recalculation(self, session_matcher, active_training_plan, strava_activity, db_session):
        """
        Should trigger adherence recalculation after successful match.
        
        Validates: Requirement 15.4 - Update adherence scores within 10 seconds
        after the Session_Matcher updates session completion status.
        """
        import time
        from app.services.adherence_calculator import AdherenceCalculator
        
        # Get initial adherence (should be 0% - no sessions completed)
        initial_adherence = AdherenceCalculator.calculate_plan_adherence(active_training_plan)
        assert initial_adherence == 0.0
        
        # Match activity
        start_time = time.time()
        matched_session_id = session_matcher.match_activity(strava_activity, user_id=1)
        elapsed_time = time.time() - start_time
        
        # Should complete within 10 seconds (requirement 15.4)
        assert elapsed_time < 10.0
        assert matched_session_id is not None
        
        # Refresh plan from database
        db_session.expire_all()
        plan = db_session.query(TrainingPlan).filter_by(id=active_training_plan.id).first()
        
        # Calculate updated adherence
        updated_adherence = AdherenceCalculator.calculate_plan_adherence(plan)
        
        # Adherence should have increased (1 out of 3 sessions completed = 33.33%)
        assert updated_adherence > initial_adherence
        assert abs(updated_adherence - 33.33) < 0.1
    
    def test_adherence_updates_for_week_and_plan(self, session_matcher, active_training_plan, strava_activity, db_session):
        """
        Should update adherence at session, week, and plan levels.
        
        Validates: Requirements 15.1, 15.2, 15.3
        """
        from app.services.adherence_calculator import AdherenceCalculator
        
        # Match activity
        matched_session_id = session_matcher.match_activity(strava_activity, user_id=1)
        assert matched_session_id is not None
        
        # Refresh from database
        db_session.expire_all()
        session = db_session.query(TrainingPlanSession).filter_by(id=matched_session_id).first()
        week = session.week
        plan = week.plan
        
        # Session adherence should be 100% (requirement 15.1)
        session_adherence = AdherenceCalculator.calculate_session_adherence(session)
        assert session_adherence == 100.0
        
        # Week adherence should be 33.33% (1 out of 3 sessions - requirement 15.2)
        week_adherence = AdherenceCalculator.calculate_week_adherence(week)
        assert abs(week_adherence - 33.33) < 0.1
        
        # Plan adherence should be 33.33% (1 out of 3 sessions - requirement 15.3)
        plan_adherence = AdherenceCalculator.calculate_plan_adherence(plan)
        assert abs(plan_adherence - 33.33) < 0.1

