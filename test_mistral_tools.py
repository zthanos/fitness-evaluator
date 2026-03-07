"""Test Mistral tool calling directly with LangChain."""
import asyncio
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

@tool
def save_athlete_goal(
    goal_type: str,
    description: str,
    target_value: float = None,
    target_date: str = None
) -> str:
    """Save a new fitness goal for the athlete. Use after gathering goal type, target, timeframe, and motivation."""
    return f"✅ Goal saved! Type: {goal_type}, Target: {target_value}, Date: {target_date}"

async def test_mistral():
    """Test Mistral with tool calling."""
    
    # Initialize Mistral
    llm = ChatOllama(
        base_url="http://localhost:11434",
        model="mistral",
        temperature=0.7,
    )
    
    # Bind tools
    llm_with_tools = llm.bind_tools([save_athlete_goal])
    
    # Simple system prompt without confusing examples
    system_prompt = """You are a fitness coach. When an athlete provides their goal information, you MUST call the save_athlete_goal tool.

DO NOT describe the tool call in text. DO NOT write "[Call save_athlete_goal...]". 
ACTUALLY INVOKE the tool using the tool calling mechanism.

Available tool:
- save_athlete_goal(goal_type, description, target_value, target_date)

When you have the information, call the tool immediately."""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="I want to lose weight from 90kg to 85kg by May 30th for the Posidonia Tour.")
    ]
    
    print("=" * 60)
    print("Testing Mistral with tool calling...")
    print("=" * 60)
    
    response = await llm_with_tools.ainvoke(messages)
    
    print("\nResponse type:", type(response))
    print("Has tool_calls attr:", hasattr(response, 'tool_calls'))
    
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print("\n✅ SUCCESS! Tool calls detected:")
        print("=" * 60)
        for tc in response.tool_calls:
            print(f"Tool: {tc['name']}")
            print(f"Args: {tc['args']}")
    else:
        print("\n❌ FAILED! No tool calls detected")
        print("=" * 60)
        print("Response content:")
        print(response.content if hasattr(response, 'content') else str(response))
        
        # Check if it's describing the call
        if hasattr(response, 'content') and '[Call' in response.content:
            print("\n⚠️  Model is DESCRIBING the tool call instead of invoking it")
            print("This is a prompt engineering issue")

if __name__ == "__main__":
    asyncio.run(test_mistral())
