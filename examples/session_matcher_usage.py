"""
Example: Using SessionMatcher to automatically match Strava activities to training sessions

This example demonstrates how the SessionMatcher service would be integrated
with the Strava sync process to automatically match imported activities to
planned training sessions.
"""
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlan
from app.models.training_plan_week import TrainingPlanWeek
from app.models.training_plan_session import TrainingPlanSession
from app.models.strava_activity import StravaActivity
from app.services.session_matcher import SessionMatcher


def setup_example_data(db_session):
    """Set up example training plan and activity."""
    # Create athlete
    athlete = Athlete(id=1, name="John Runner", email="john@example.com")
    db_session.add(athlete)
    
    # Create active training plan (starts on Monday, March 4, 2024)
    plan = TrainingPlan(
        user_id=1,
        title="10K Training Plan",
        sport="running",
        start_date=date(2024, 3, 4),  # Monday
        end_date=date(2024, 5, 4),
        status="active"
    )
    db_session.add(plan)
    db_session.flush()
    
    # Add week 1
    week1 = TrainingPlanWeek(
        plan_id=plan.id,
        week_number=1,
        focus="Base building",
        volume_target=15.0
    )
    db_session.add(week1)
    db_session.flush()
    
    # Add Monday easy run session
    monday_session = TrainingPlanSession(
        week_id=week1.id,
        day_of_week=1,  # Monday
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy",
        description="Easy pace, focus on form"
    )
    db_session.add(monday_session)
    
    # Add Wednesday tempo run session
    wednesday_session = TrainingPlanSession(
        week_id=week1.id,
        day_of_week=3,  # Wednesday
        session_type="tempo_run",
        duration_minutes=60,
        intensity="moderate",
        description="Tempo pace for 30 minutes"
    )
    db_session.add(wednesday_session)
    
    db_session.commit()
    
    # Simulate Strava activity import (Monday morning run)
    # March 1, 2024 is a Friday, so Monday of week 1 is March 4
    activity = StravaActivity(
        athlete_id=1,
        strava_id=987654321,
        activity_type="Run",
        start_date=datetime(2024, 3, 4, 12, 0, 0),  # Monday March 4, noon (matches scheduled time)
        moving_time_s=2700,  # 45 minutes
        distance_m=7200,  # 7.2km
        avg_hr=135,  # Easy intensity
        max_hr=175,
        raw_json="{}"
    )
    db_session.add(activity)
    db_session.commit()
    
    return plan, activity


def main():
    """Run the example."""
    # Set up in-memory database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 70)
    print("Session Matcher Example")
    print("=" * 70)
    
    # Set up example data
    print("\n1. Setting up example training plan and Strava activity...")
    plan, activity = setup_example_data(db_session)
    print(f"   ✓ Created training plan: {plan.title}")
    print(f"   ✓ Imported Strava activity: {activity.activity_type} on {activity.start_date}")
    
    # Create session matcher
    matcher = SessionMatcher(db_session)
    
    # Find candidate sessions
    print("\n2. Finding candidate sessions for matching...")
    candidates = matcher.find_candidate_sessions(activity, user_id=1)
    print(f"   ✓ Found {len(candidates)} candidate session(s)")
    
    # Calculate confidence for each candidate
    print("\n3. Calculating match confidence scores...")
    for candidate in candidates:
        confidence = matcher.calculate_match_confidence(activity, candidate)
        print(f"   • {candidate.session_type} (Day {candidate.day_of_week}): {confidence:.1f}%")
    
    # Match activity
    print("\n4. Attempting to match activity to session...")
    matched_session_id = matcher.match_activity(activity, user_id=1)
    
    if matched_session_id:
        matched_session = db_session.query(TrainingPlanSession).filter_by(id=matched_session_id).first()
        print(f"   ✓ Successfully matched!")
        print(f"   • Session: {matched_session.session_type}")
        print(f"   • Duration: {matched_session.duration_minutes} minutes (planned)")
        print(f"   • Intensity: {matched_session.intensity}")
        print(f"   • Completed: {matched_session.completed}")
        print(f"   • Matched Activity ID: {matched_session.matched_activity_id}")
    else:
        print("   ✗ No match found (confidence below 80%)")
    
    # Show updated plan status
    print("\n5. Training plan status:")
    all_sessions = (
        db_session.query(TrainingPlanSession)
        .join(TrainingPlanWeek)
        .filter(TrainingPlanWeek.plan_id == plan.id)
        .all()
    )
    completed_count = sum(1 for s in all_sessions if s.completed)
    total_count = len(all_sessions)
    adherence = (completed_count / total_count * 100) if total_count > 0 else 0
    
    print(f"   • Total sessions: {total_count}")
    print(f"   • Completed sessions: {completed_count}")
    print(f"   • Adherence: {adherence:.1f}%")
    
    print("\n" + "=" * 70)
    print("Example completed successfully!")
    print("=" * 70)
    
    db_session.close()


if __name__ == "__main__":
    main()
