"""Test script to verify LangChain tool calling with different models."""
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.langchain_chat_service import LangChainChatService
from app.database import Base

# Create test database
engine = create_engine("sqlite:///./test_tool_calling.db")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

async def test_tool_calling():
    """Test tool calling with current model."""
    db = SessionLocal()
    
    try:
        service = LangChainChatService(db)
        
        # Test message that should trigger tool calling
        messages = [
            {
                'role': 'user',
                'content': 'I want to lose weight. I am currently 90.5kg and want to reach 85kg by May 30th for the Posidonia Tour.'
            }
        ]
        
        print("=" * 60)
        print("Testing tool calling with current model...")
        print("=" * 60)
        
        response = await service.get_chat_response(messages)
        
        print("\n" + "=" * 60)
        print("RESPONSE:")
        print("=" * 60)
        print(response.get('content', ''))
        
        if 'tool_calls' in response:
            print("\n" + "=" * 60)
            print("✅ TOOL CALLS DETECTED:")
            print("=" * 60)
            for tool_call in response['tool_calls']:
                print(f"Tool: {tool_call['name']}")
                print(f"Args: {tool_call['args']}")
        else:
            print("\n" + "=" * 60)
            print("❌ NO TOOL CALLS - Model did not use tools")
            print("=" * 60)
            
            # Check if response mentions saving
            content_lower = response.get('content', '').lower()
            if any(phrase in content_lower for phrase in ['save', 'goal', 'set up']):
                print("\n⚠️  Model MENTIONED saving but didn't call the tool")
                print("This suggests the model doesn't support tool calling well")
                print("\nRECOMMENDATION: Switch to 'mistral' model")
                print("Update .env: OLLAMA_MODEL=mistral")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_tool_calling())
