"""Integration tests for Task 17.2: Wire Training Plan Engine to Chat Tools

Tests the integration of Training Plan Engine with Chat Tools:
- Plan generation integrated into save_training_plan tool
- Plan retrieval integrated into get_training_plan tool
- Plan generation flow with confirmation

Requirements: 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3, 9.4
"""
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.base import Base
from app.models.athlete import Athlete
from app.models.athlete_goal import AthleteGoal
from app.ai.tools.save_training_plan import save_training_plan
from app.ai.tools.get_training_plan import get_training_plan
from app.services.training_plan_engine import TrainingPlanEngine


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_athlete(db_session: Session):
    """Create a test athlete."""
    athlete = Athlete(
        id=888,
        name="Test Runner",
        email="runner@example.com",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(athlete)
    db_session.commit()
    return athlete


@pytest.fixture
def test_goal(db_session: Session, test_athlete: Athlete):
    """Create a test goal."""
    goal = AthleteGoal(
        id="goal-123",
        athlete_id=str(test_athlete.id),
        goal_type="performance",
        description="Run a sub-4 hour marathon",
        target_value=240.0,  # 4 hours in minutes
        target_date=date.today() + timedelta(days=90),
        status="active",
        created_at=datetime.utcnow()
    )
    db_session.add(goal)
    db_session.commit()
    return goal


def test_save_training_plan_tool_integration(test_athlete: Athlete, test_goal: AthleteGoal):
    """Test that save_training_plan tool is properly wired to Training Plan Engine."""
    # Prepare plan data
    start_date = date.today() + timedelta(days=7)
    
    weeks_data = [
        {
            "week_number": 1,
            "focus": "Base building",
            "volume_target": 5.0,
            "sessions": [
                {
                    "day_of_week": 1,
                    "session_type": "easy_run",
                    "duration_minutes": 45,
                    "intensity": "easy",
                    "description": "Easy pace, focus on form"
                },
                {
                    "day_of_week": 3,
                    "session_type": "tempo_run",
                    "duration_minutes": 60,
                    "intensity": "moderate",
                    "description": "Tempo run at threshold pace"
                },
                {
                    "day_of_week": 6,
                    "session_type": "long_run",
                    "duration_minutes": 90,
                    "intensity": "easy",
                    "description": "Long slow distance run"
                }
            ]
        },
        {
            "week_number": 2,
            "focus": "Building endurance",
            "volume_target": 6.0,
            "sessions": [
                {
                    "day_of_week": 1,
                    "session_type": "easy_run",
                    "duration_minutes": 50,
                    "intensity": "easy",
                    "description": "Easy recovery run"
                },
                {
                    "day_of_week": 3,
                    "session_type": "interval",
                    "duration_minutes": 60,
                    "intensity": "hard",
                    "description": "5x1000m intervals at 5K pace"
                },
                {
                    "day_of_week": 6,
                    "session_type": "long_run",
                    "duration_minutes": 100,
                    "intensity": "easy",
                    "description": "Progressive long run"
                }
            ]
        }
    ]
    
    # Call save_training_plan tool
    result = save_training_plan.invoke({
        "user_id": test_athlete.id,
        "title": "Marathon Training Plan",
        "sport": "running",
        "start_date": start_date.isoformat(),
        "duration_weeks": 2,
        "weeks": weeks_data,
        "goal_id": test_goal.id,
        "status": "active"
    })
    
    # Print result for debugging
    if not result.get("success"):
        print(f"\nError: {result.get('message')}")
        print(f"Full result: {result}")
    
    # Verify result
    assert result["success"] is True, f"Tool failed: {result.get('message', 'Unknown error')}"
    assert "plan_id" in result
    assert result["plan"]["title"] == "Marathon Training Plan"
    assert result["plan"]["sport"] == "running"
    assert result["plan"]["weeks_count"] == 2
    
    print(f"✓ Saved training plan with ID: {result['plan_id']}")
    
    return result["plan_id"]


def test_get_training_plan_tool_integration(test_athlete: Athlete, test_goal: AthleteGoal):
    """Test that get_training_plan tool is properly wired to Training Plan Engine."""
    # First save a plan
    plan_id = test_save_training_plan_tool_integration(test_athlete, test_goal)
    
    # Now retrieve it using get_training_plan tool
    result = get_training_plan.invoke({
        "user_id": test_athlete.id,
        "plan_id": plan_id
    })
    
    # Verify result
    assert result is not None
    assert result["id"] == plan_id
    assert result["title"] == "Marathon Training Plan"
    assert result["sport"] == "running"
    assert result["user_id"] == test_athlete.id
    assert result["goal_id"] == test_goal.id
    assert len(result["weeks"]) == 2
    
    # Verify week 1
    week1 = result["weeks"][0]
    assert week1["week_number"] == 1
    assert week1["focus"] == "Base building"
    assert len(week1["sessions"]) == 3
    
    # Verify a session
    session1 = week1["sessions"][0]
    assert session1["day_of_week"] == 1
    assert session1["session_type"] == "easy_run"
    assert session1["duration_minutes"] == 45
    assert session1["intensity"] == "easy"
    assert session1["completed"] is False
    
    print(f"✓ Retrieved training plan with {len(result['weeks'])} weeks")


def test_plan_generation_flow_with_confirmation(test_athlete: Athlete, test_goal: AthleteGoal):
    """Test the plan generation flow with confirmation.
    
    This simulates the flow:
    1. LLM generates a plan (using Training Plan Engine)
    2. Plan is presented to athlete for review
    3. Athlete confirms
    4. Plan is saved using save_training_plan tool
    """
    # Step 1: Generate plan (simulated - in real flow this would use LLM)
    start_date = date.today() + timedelta(days=7)
    
    # Simulated generated plan
    generated_plan_data = {
        "user_id": test_athlete.id,
        "title": "10K Training Plan",
        "sport": "running",
        "start_date": start_date.isoformat(),
        "duration_weeks": 4,
        "weeks": [
            {
                "week_number": i + 1,
                "focus": f"Week {i + 1} focus",
                "volume_target": 4.0 + i,
                "sessions": [
                    {
                        "day_of_week": 2,
                        "session_type": "easy_run",
                        "duration_minutes": 30 + (i * 5),
                        "intensity": "easy",
                        "description": f"Easy run week {i + 1}"
                    },
                    {
                        "day_of_week": 5,
                        "session_type": "tempo_run",
                        "duration_minutes": 40 + (i * 5),
                        "intensity": "moderate",
                        "description": f"Tempo run week {i + 1}"
                    }
                ]
            }
            for i in range(4)
        ],
        "goal_id": test_goal.id,
        "status": "active"
    }
    
    # Step 2: Present to athlete (simulated - in real flow this would be shown in UI)
    print(f"\n📋 Generated Plan: {generated_plan_data['title']}")
    print(f"   Duration: {generated_plan_data['duration_weeks']} weeks")
    print(f"   Sport: {generated_plan_data['sport']}")
    print(f"   Weeks: {len(generated_plan_data['weeks'])}")
    
    # Step 3: Athlete confirms (simulated)
    athlete_confirmed = True
    
    # Step 4: Save plan using tool
    if athlete_confirmed:
        result = save_training_plan.invoke(generated_plan_data)
        
        assert result["success"] is True
        assert "plan_id" in result
        
        print(f"✓ Plan confirmed and saved with ID: {result['plan_id']}")
        
        # Verify plan was saved correctly
        retrieved_plan = get_training_plan.invoke({
            "user_id": test_athlete.id,
            "plan_id": result["plan_id"]
        })
        
        assert retrieved_plan is not None
        assert retrieved_plan["title"] == "10K Training Plan"
        assert len(retrieved_plan["weeks"]) == 4
        
        print(f"✓ Plan generation flow with confirmation completed successfully")


def test_user_scoping_in_plan_tools(test_athlete: Athlete, test_goal: AthleteGoal):
    """Test that plan tools properly scope by user_id."""
    # Create a plan for test_athlete
    plan_id = test_save_training_plan_tool_integration(test_athlete, test_goal)
    
    # Try to retrieve as a different user
    different_user_id = 999
    
    result = get_training_plan.invoke({
        "user_id": different_user_id,
        "plan_id": plan_id
    })
    
    # Should return None because plan belongs to different user
    assert result is None
    
    print(f"✓ User scoping verified - different user cannot access plan")


def test_plan_with_goal_linking(test_athlete: Athlete, test_goal: AthleteGoal):
    """Test that plans are properly linked to goals."""
    # Save a plan with goal_id
    start_date = date.today() + timedelta(days=7)
    
    result = save_training_plan.invoke({
        "user_id": test_athlete.id,
        "title": "Goal-Linked Plan",
        "sport": "running",
        "start_date": start_date.isoformat(),
        "duration_weeks": 1,
        "weeks": [
            {
                "week_number": 1,
                "focus": "Test week",
                "volume_target": 3.0,
                "sessions": [
                    {
                        "day_of_week": 1,
                        "session_type": "easy_run",
                        "duration_minutes": 30,
                        "intensity": "easy",
                        "description": "Test session"
                    }
                ]
            }
        ],
        "goal_id": test_goal.id,
        "status": "active"
    })
    
    assert result["success"] is True
    plan_id = result["plan_id"]
    
    # Retrieve and verify goal link
    retrieved_plan = get_training_plan.invoke({
        "user_id": test_athlete.id,
        "plan_id": plan_id
    })
    
    assert retrieved_plan["goal_id"] == test_goal.id
    
    print(f"✓ Plan properly linked to goal: {test_goal.id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
