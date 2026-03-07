"""Quick test script for Goals API endpoints"""
import asyncio
from datetime import date, timedelta
from app.database import SessionLocal
from app.services.goal_service import GoalService

async def test_goals():
    """Test goal creation and retrieval"""
    db = SessionLocal()
    
    try:
        goal_service = GoalService(db)
        
        # Test 1: Create a weight loss goal
        print("Test 1: Creating weight loss goal...")
        result = goal_service.save_goal(
            goal_type="weight_loss",
            description="Lose 10kg in 3 months for wedding. Currently 85kg, target 75kg.",
            target_value=75.0,
            target_date=(date.today() + timedelta(days=90)).isoformat()
        )
        print(f"✅ Goal created: {result['goal_id']}")
        print(f"   Description: {result['goal']['description']}")
        
        # Test 2: Get active goals
        print("\nTest 2: Retrieving active goals...")
        active_goals = goal_service.get_active_goals()
        print(f"✅ Found {len(active_goals)} active goal(s)")
        for goal in active_goals:
            print(f"   - {goal.goal_type}: {goal.description[:50]}...")
        
        # Test 3: Update goal status
        print("\nTest 3: Marking goal as completed...")
        update_result = goal_service.update_goal_status(result['goal_id'], 'completed')
        print(f"✅ Goal status updated: {update_result['message']}")
        
        # Test 4: Get tool definition
        print("\nTest 4: Getting LLM tool definition...")
        tool_def = GoalService.get_tool_definition()
        print(f"✅ Tool name: {tool_def['function']['name']}")
        print(f"   Required params: {tool_def['function']['parameters']['required']}")
        
        print("\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_goals())
