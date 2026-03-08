"""
Example: Using Tool Configuration in Context Engineering Services

This example demonstrates how to use the tool configuration system
in Context Engineering services to get enabled tools based on intent.
"""

from typing import List, Optional
from langchain_core.tools import BaseTool
from app.ai.tools import get_enabled_tools, is_web_search_enabled
from app.ai.retrieval.intent_router import IntentRouter, Intent


class ExampleChatService:
    """
    Example chat service using Context Engineering tools.
    
    This demonstrates how to integrate the tool configuration system
    with LangChain-based services.
    """
    
    def __init__(self):
        self.intent_router = IntentRouter()
    
    def get_tools_for_query(self, query: str) -> List[BaseTool]:
        """
        Get appropriate tools for a query based on intent classification.
        
        This method:
        1. Classifies the query intent
        2. Gets enabled tools for that intent
        3. Returns the filtered tool list
        
        Args:
            query: User query text
            
        Returns:
            List of enabled tools appropriate for the query intent
        """
        # Classify the query intent
        intent = self.intent_router.classify(query)
        
        # Get enabled tools for this intent
        # Note: Web search is disabled by default, but if enabled in the future,
        # it would only be available for specific intents
        tools = get_enabled_tools(intent=intent.value if intent else None)
        
        # Log which tools are available
        print(f"Query intent: {intent.value if intent else 'unknown'}")
        print(f"Available tools: {[tool.name for tool in tools]}")
        
        # Check if web search is available (will be False by default)
        if is_web_search_enabled(intent=intent.value if intent else None):
            print("Web search is enabled for this intent")
        else:
            print("Web search is disabled (using internal data only)")
        
        return tools
    
    def create_llm_with_tools(self, query: str):
        """
        Create an LLM instance with appropriate tools bound.
        
        This is how you would integrate with LangChain's bind_tools.
        
        Args:
            query: User query text
            
        Returns:
            LLM instance with tools bound
        """
        from langchain_ollama import ChatOllama
        
        # Get tools for this query
        tools = self.get_tools_for_query(query)
        
        # Create LLM instance
        llm = ChatOllama(
            model="mixtral:8x7b-instruct",
            base_url="http://localhost:11434",
            temperature=0.7
        )
        
        # Bind tools to LLM
        llm_with_tools = llm.bind_tools(tools)
        
        return llm_with_tools


# Example usage
if __name__ == "__main__":
    service = ExampleChatService()
    
    # Example 1: Recent performance query (uses internal data only)
    print("\n=== Example 1: Recent Performance Query ===")
    query1 = "How did I perform in my last week of training?"
    tools1 = service.get_tools_for_query(query1)
    print(f"Tools available: {len(tools1)}")
    
    # Example 2: General query (uses internal data only)
    print("\n=== Example 2: General Query ===")
    query2 = "What are my current goals?"
    tools2 = service.get_tools_for_query(query2)
    print(f"Tools available: {len(tools2)}")
    
    # Example 3: Research query (web search disabled by default)
    print("\n=== Example 3: Research Query ===")
    query3 = "What are the latest studies on marathon training?"
    tools3 = service.get_tools_for_query(query3)
    print(f"Tools available: {len(tools3)}")
    print("Note: Web search is disabled by default for security")
    
    # Example 4: Direct tool access (no intent classification)
    print("\n=== Example 4: Direct Tool Access ===")
    from app.ai.tools import get_enabled_tools
    all_tools = get_enabled_tools()
    print(f"All enabled tools: {[tool.name for tool in all_tools]}")


# Future: Enabling web search for specific intents
"""
To enable web search for specific intents in the future, update
app/ai/config/model_profiles.yaml:

tools:
  enabled_categories:
    - "data_retrieval"
    - "web_search"  # Uncomment to enable
  
  web_search:
    enabled: true  # Change to true
    intent_gating: true
    allowed_intents:
      - "research"  # Allow for research queries
      - "external_info"  # Allow for external info queries

Then queries classified as "research" or "external_info" would have
access to web search tools, while all other intents would use
internal data only.
"""
