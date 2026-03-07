"""Minimal test to see if Mistral supports tool calling at all."""
import asyncio
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

@tool
def get_weather(location: str) -> str:
    """Get the weather for a location."""
    return f"Weather in {location}: Sunny, 25°C"

async def test():
    llm = ChatOllama(
        base_url="http://localhost:11434",
        model="mistral",
        temperature=0,
    )
    
    llm_with_tools = llm.bind_tools([get_weather])
    
    # Very simple request
    response = await llm_with_tools.ainvoke([
        HumanMessage(content="What's the weather in Paris?")
    ])
    
    print("Response:", response)
    print("\nHas tool_calls:", hasattr(response, 'tool_calls'))
    if hasattr(response, 'tool_calls'):
        print("Tool calls:", response.tool_calls)
    print("\nContent:", response.content if hasattr(response, 'content') else "No content")

asyncio.run(test())
