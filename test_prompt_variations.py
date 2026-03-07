"""Test different prompt variations to find what works."""
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
    """Save a new fitness goal for the athlete."""
    return f"✅ Goal saved! Type: {goal_type}, Target: {target_value}, Date: {target_date}"

async def test_prompt(prompt_name: str, system_prompt: str):
    """Test a specific prompt variation."""
    llm = ChatOllama(
        base_url="http://localhost:11434",
        model="mistral",
        temperature=0,
    )
    
    llm_with_tools = llm.bind_tools([save_athlete_goal])
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="I want to lose weight from 90.5kg to 85kg by May 30th 2026 for the Posidonia Tour.")
    ]
    
    response = await llm_with_tools.ainvoke(messages)
    
    has_tool_calls = hasattr(response, 'tool_calls') and response.tool_calls
    
    print(f"\n{'='*70}")
    print(f"PROMPT: {prompt_name}")
    print(f"{'='*70}")
    print(f"Result: {'✅ TOOL CALLED' if has_tool_calls else '❌ NO TOOL CALL'}")
    
    if has_tool_calls:
        print(f"Tool: {response.tool_calls[0]['name']}")
        print(f"Args: {response.tool_calls[0]['args']}")
    else:
        content = response.content[:200] if hasattr(response, 'content') else str(response)[:200]
        print(f"Response: {content}...")
    
    return has_tool_calls

async def main():
    """Test all prompt variations."""
    
    prompts = {
        "1. Minimal": "You are a fitness coach. Use save_athlete_goal tool when athletes tell you their goals.",
        
        "2. With goal types": """You are a fitness coach. Use save_athlete_goal tool to save goals.
Goal types: weight_loss, weight_gain, performance, endurance, strength, custom.""",
        
        "3. With instructions": """You are a fitness coach helping athletes set goals.

When an athlete provides their goal information, use the save_athlete_goal tool to save it.

Goal types: weight_loss, weight_gain, performance, endurance, strength, custom
For weight goals, target_value is the target weight in kg.
Use YYYY-MM-DD format for dates.""",
        
        "4. With personality": """You are a friendly fitness coach helping athletes achieve their goals.

When an athlete shares their goal, use the save_athlete_goal tool to save it to the database.

Goal types: weight_loss, weight_gain, performance, endurance, strength, custom
For weight goals, target_value is the target weight in kg.
Use YYYY-MM-DD format for dates.

Be encouraging and supportive!""",
        
        "5. With examples (text)": """You are a fitness coach. Use save_athlete_goal to save goals.

Goal types: weight_loss, weight_gain, performance, endurance, strength, custom

Example: If athlete says "I want to lose 5kg by June", call save_athlete_goal with:
- goal_type: "weight_loss"
- target_value: (their target weight in kg)
- target_date: "2026-06-01"
- description: "Lose 5kg by June"

Be supportive!""",
    }
    
    results = {}
    for name, prompt in prompts.items():
        results[name] = await test_prompt(name, prompt)
        await asyncio.sleep(1)  # Brief pause between tests
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for name, success in results.items():
        status = "✅ WORKS" if success else "❌ FAILS"
        print(f"{status} - {name}")
    
    # Find the most complex working prompt
    working_prompts = [name for name, success in results.items() if success]
    if working_prompts:
        print(f"\n🎯 Best prompt: {working_prompts[-1]}")
    else:
        print("\n⚠️  No prompts worked!")

if __name__ == "__main__":
    asyncio.run(main())
