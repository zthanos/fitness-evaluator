"""Full integration test for goal setting with tool calling."""
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.langchain_chat_service import LangChainChatService
from app.models.base import Base
from app.models.athlete_goal import AthleteGoal

# Create test database
engine = create_engine("sqlite:///./test_integration.db")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

async def test_full_flow():
    """Test the complete goal setting flow."""
    db = SessionLocal()
    
    try:
        # Clear any existing goals
        db.query(AthleteGoal).delete()
        db.commit()
        
        service = LangChainChatService(db)
        
        # Test with the exact user message from logs
        messages = [
            {
                'role': 'user',
                'content': 'I want to lose weight from 90.5kg to 85kg by May 30th 2026 for the Posidonia Tour.'
            }
        ]
        
        print("=" * 70)
        print("FULL INTEGRATION TEST")
        print("=" * 70)
        print("\nUser message:")
        print(messages[0]['content'])
        print("\n" + "=" * 70)
        print("Calling LangChain service...")
        print("=" * 70)
        
        response = await service.get_chat_response(messages)
        
        print("\n" + "=" * 70)
        print("RESPONSE:")
        print("=" * 70)
        print(response.get('content', ''))
        
        # Check for tool calls
        if 'tool_calls' in response and response['tool_calls']:
            print("\n" + "=" * 70)
            print("✅ SUCCESS! Tool was called")
            print("=" * 70)
            for tc in response['tool_calls']:
                print(f"\nTool: {tc['name']}")
                print(f"Arguments:")
                for key, value in tc['args'].items():
                    print(f"  - {key}: {value}")
            
            # Check if goal was saved to database
            goals = db.query(AthleteGoal).all()
            print(f"\n✅ Goals in database: {len(goals)}")
            if goals:
                goal = goals[0]
                print(f"\nSaved goal details:")
                print(f"  - ID: {goal.id}")
                print(f"  - Type: {goal.goal_type}")
                print(f"  - Target: {goal.target_value}kg")
                print(f"  - Date: {goal.target_date}")
                print(f"  - Description: {goal.description[:100]}...")
        else:
            print("\n" + "=" * 70)
            print("❌ FAILED! No tool calls detected")
            print("=" * 70)
            
            # Check if it's describing the call
            content = response.get('content', '')
            if '[Call' in content or 'save_athlete_goal' in content:
                print("\n⚠️  Model is DESCRIBING the tool call instead of invoking it")
                print("\nThis means the prompt is still confusing the model.")
                print("The model output contains:")
                print(content[:300])
            else:
                print("\nModel response doesn't mention tools at all.")
                print("This could be a LangChain configuration issue.")
        
        print("\n" + "=" * 70)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_full_flow())
