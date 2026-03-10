"""
SearchWeb LangChain StructuredTool for web search using Tavily API.

This tool allows the LLM to search for current fitness information, training
advice, nutrition guidance, and sports science research.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from app.config import get_settings
from app.ai.telemetry import get_tool_logger


class SearchWebInput(BaseModel):
    """Input schema for SearchWeb tool."""
    
    query: str = Field(
        ...,
        description="Search query for fitness, training, nutrition, or sports science information",
        min_length=1
    )
    max_results: int = Field(
        3,
        description="Maximum number of search results to return (default: 3)",
        gt=0,
        le=10
    )


@tool(args_schema=SearchWebInput)
def search_web(query: str, max_results: int = 3) -> str:
    """
    Search the web for current fitness information.
    
    This tool uses the Tavily Search API to find up-to-date information about
    fitness, training, nutrition, or sports science. Results include source
    citations for credibility.
    
    Use this when you need:
    - Current training methodologies or research
    - Nutrition advice or dietary information
    - Sports science findings
    - Equipment recommendations
    - Injury prevention or recovery information
    
    Args:
        query: Search query for fitness-related information
        max_results: Maximum number of results to return (default: 3, max: 10)
        
    Returns:
        Formatted search results with titles, content, and source URLs
    """
    # Get tool logger
    logger = get_tool_logger()
    
    # Get settings
    settings = get_settings()
    
    try:
        # Check if Tavily API key is configured
        if not settings.TAVILY_API_KEY:
            result = (
                "⚠️ Web search is not configured. To enable web search, set TAVILY_API_KEY "
                "in your .env file. Get a free API key at https://tavily.com"
            )
            
            # Log invocation with configuration error
            logger.log_invocation(
                tool_name="search_web",
                parameters={"query": query, "max_results": max_results},
                result={"error": "API key not configured"}
            )
            
            return result
        
        # Try to import and use Tavily
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults
            
            # Create Tavily search tool
            search = TavilySearchResults(
                api_key=settings.TAVILY_API_KEY,
                max_results=max_results
            )
            
            # Execute search
            results = search.invoke(query)
            
            # Format results with source citations
            formatted_parts = [f"Web search results for '{query}':\n"]
            
            if not results:
                formatted_parts.append("No results found.")
            else:
                for i, result in enumerate(results, 1):
                    title = result.get('title', 'No title')
                    content = result.get('content', 'No content')
                    url = result.get('url', 'No URL')
                    
                    formatted_parts.append(f"\n{i}. **{title}**")
                    formatted_parts.append(f"   {content}")
                    formatted_parts.append(f"   📎 Source: {url}")
            
            formatted_result = "\n".join(formatted_parts)
            
            # Log successful invocation
            logger.log_invocation(
                tool_name="search_web",
                parameters={"query": query, "max_results": max_results},
                result={"results_count": len(results) if results else 0}
            )
            
            return formatted_result
            
        except ImportError:
            result = (
                "⚠️ Tavily search library is not installed. "
                "Install with: pip install langchain-community"
            )
            
            # Log invocation with import error
            logger.log_invocation(
                tool_name="search_web",
                parameters={"query": query, "max_results": max_results},
                result={"error": "Library not installed"}
            )
            
            return result
            
    except Exception as e:
        error_message = f"❌ Web search error: {str(e)}"
        
        # Log failed invocation
        logger.log_invocation(
            tool_name="search_web",
            parameters={"query": query, "max_results": max_results},
            result=None,
            error=e
        )
        
        return error_message
