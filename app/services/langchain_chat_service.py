"""LangChain-based Chat Service with Agentic Tool Calling

Uses LangChain to create an agentic AI coach that can reliably call tools.
Supports both Ollama and LM Studio (OpenAI-compatible) backends.
Uses ReAct agent for better tool calling with models that need guidance.
Provides better tool calling support than raw LLM API calls.
"""
import asyncio
import json
from typing import List, Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session

try:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    from langchain_core.tools import tool as langchain_tool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("[LangChain] Not available, tool calling may be less reliable")

from app.services.goal_service import GoalService
from app.services.rag_service import RAGSystem
from app.config import get_settings


class LangChainChatService:
    """
    LangChain-based chat service with tool calling.
    
    Uses LangChain's ChatOllama with bind_tools for reliable tool execution.
    """
    
    def __init__(self, db: Session):
        """
        Initialize LangChain chat service.
        
        Args:
            db: SQLAlchemy database session
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is not available. Install with: uv pip install langchain-core langchain-ollama langchain-openai")
        
        self.db = db
        self.goal_service = GoalService(db)
        self.settings = get_settings()
        
        # Initialize RAG system for context retrieval
        try:
            self.rag_system = RAGSystem(db)
            print("[LangChain] RAG system initialized")
        except Exception as e:
            print(f"[LangChain] RAG system initialization failed: {e}")
            self.rag_system = None
        
        # Determine which LLM backend to use
        llm_type = self.settings.LLM_TYPE.lower()
        
        if llm_type == "lm-studio" or llm_type == "openai":
            # Use OpenAI-compatible endpoint (LM Studio)
            print(f"[LangChain] Initializing with LM Studio/OpenAI backend")
            # Note: LangChain's ChatOpenAI automatically adds /chat/completions to base_url
            # So if base_url is http://localhost:1234/v1, it becomes http://localhost:1234/v1/chat/completions
            base_url = self.settings.llm_base_url
            # Remove /v1 if it's already in the URL since ChatOpenAI handles it
            if base_url.endswith('/v1'):
                base_url = base_url[:-3]
            
            self.llm = ChatOpenAI(
                base_url=base_url,
                api_key="lm-studio",  # LM Studio doesn't require a real key
                model=self.settings.OLLAMA_MODEL,  # Model name from settings
                temperature=0.1,  # Low temperature for reliable tool calling
            )
            print(f"[LangChain] Using base_url: {base_url}")
        else:
            # Use Ollama backend (default)
            print(f"[LangChain] Initializing with Ollama backend")
            self.llm = ChatOllama(
                base_url=self.settings.llm_base_url,
                model=self.settings.OLLAMA_MODEL,
                temperature=0.1,  # Low temperature for reliable tool calling
            )
        
        # Create and bind tools
        self.tools = self._create_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        print(f"[LangChain] Initialized with {len(self.tools)} tools")
        print(f"[LangChain] Backend: {llm_type}, Endpoint: {self.settings.llm_base_url}, Model: {self.settings.OLLAMA_MODEL}")
    
    def _create_tools(self):
        """Create LangChain tools."""
        
        @langchain_tool
        def save_athlete_goal(
            goal_type: str,
            description: str,
            target_value: float = None,
            target_date: str = None
        ) -> str:
            """Save a new fitness goal for the athlete. Use after gathering goal type, target, timeframe, and motivation."""
            try:
                result = self.goal_service.save_goal(
                    goal_type=goal_type,
                    description=description,
                    target_value=target_value,
                    target_date=target_date
                )
                
                if result['success']:
                    return f"✅ Goal saved! ID: {result['goal_id']}"
                else:
                    return f"❌ Failed: {result.get('message', 'Unknown error')}"
                    
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        return [save_athlete_goal]
    
    async def get_chat_response(
        self,
        messages: List[Dict[str, str]],
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Get chat response with tool calling and RAG context.
        
        Args:
            messages: Conversation history
            use_rag: Whether to use RAG context retrieval
        
        Returns:
            Response dict
        """
        try:
            # Get RAG context if enabled and available
            rag_context = ""
            if use_rag and self.rag_system and messages:
                # Use the last user message as query
                last_user_message = None
                for msg in reversed(messages):
                    if msg['role'] == 'user':
                        last_user_message = msg['content']
                        break
                
                if last_user_message:
                    print(f"[LangChain] Retrieving RAG context for: {last_user_message[:50]}...")
                    results = self.rag_system.search(last_user_message, top_k=5)
                    
                    if results:
                        rag_context = self._format_rag_context(results)
                        print(f"[LangChain] Retrieved {len(results)} relevant records")
            
            # Load system prompt
            system_prompt = self._load_system_prompt(rag_context)
            
            # Convert to LangChain messages
            lc_messages = [SystemMessage(content=system_prompt)]
            
            for msg in messages:
                if msg['role'] == 'user':
                    lc_messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    lc_messages.append(AIMessage(content=msg['content']))
            
            # Call LLM with tools
            print(f"[LangChain] Invoking LLM with {len(lc_messages)} messages")
            print(f"[LangChain] Tools available: {[t.name for t in self.tools]}")
            response = await self.llm_with_tools.ainvoke(lc_messages)
            
            # Check for tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                print(f"[LangChain] Tool calls detected: {len(response.tool_calls)}")
                
                # Execute tools
                tool_results = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    
                    print(f"[LangChain] Executing tool: {tool_name}")
                    print(f"[LangChain] Args: {tool_args}")
                    
                    # Find and execute tool
                    for tool in self.tools:
                        if tool.name == tool_name:
                            result = tool.invoke(tool_args)
                            tool_results.append(result)
                            print(f"[LangChain] Tool result: {result}")
                
                # Add tool results to conversation and get final response
                lc_messages.append(response)
                for i, result in enumerate(tool_results):
                    lc_messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=response.tool_calls[i]['id']
                    ))
                
                # Get final response after tool execution
                final_response = await self.llm_with_tools.ainvoke(lc_messages)
                
                return {
                    'content': final_response.content,
                    'messages': messages,
                    'tool_calls': response.tool_calls,
                    'tool_results': tool_results
                }
            else:
                print("[LangChain] No tool calls detected")
                content = response.content if hasattr(response, 'content') else str(response)
                print("[LangChain] Response content preview:", content[:200] if len(content) > 200 else content)
                
                # Check if response mentions saving a goal but didn't call the tool
                content_lower = content.lower()
                if any(phrase in content_lower for phrase in ['save this goal', 'save the goal', 'let me save', "i'll save"]):
                    print("[LangChain] WARNING: LLM mentioned saving goal but didn't call tool")
                    print("[LangChain] Try using 'mistral' model which has better tool calling support")
                
                # No tool calls, return response
                return {
                    'content': content,
                    'messages': messages
                }
            
        except Exception as e:
            print(f"[LangChain] Error: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'content': f"I encountered an error: {str(e)}. Please make sure the LLM is running.",
                'messages': messages,
                'error': str(e)
            }
    
    async def stream_chat_response(
        self,
        messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Stream response."""
        response = await self.get_chat_response(messages)
        content = response.get('content', '')
        
        # Simulate streaming
        words = content.split(' ')
        for i, word in enumerate(words):
            if i > 0:
                yield ' '
            yield word
            await asyncio.sleep(0.02)
    
    def _load_system_prompt(self, rag_context: str = "") -> str:
        """
        Load system prompt with optional RAG context, athlete profile, and active goals.
        
        Args:
            rag_context: Formatted RAG context to include
        
        Returns:
            System prompt string
        """
        try:
            with open('app/prompts/goal_setting_prompt.txt', 'r', encoding='utf-8') as f:
                base_prompt = f.read()
        except FileNotFoundError:
            base_prompt = """You are an expert fitness coach. When athletes want to set goals, gather information and use the save_athlete_goal tool."""
        
        # Get athlete profile information (for now, using default athlete)
        athlete_profile = self._get_athlete_profile()
        
        # Get active goals
        active_goals = self._get_active_goals_context()
        
        # Build enhanced system prompt
        enhanced_prompt = base_prompt
        
        # Add athlete profile
        if athlete_profile:
            enhanced_prompt += f"\n\n## Athlete Profile\n\n{athlete_profile}"
        
        # Add active goals
        if active_goals:
            enhanced_prompt += f"\n\n## Active Goals\n\n{active_goals}"
        
        # Add RAG context if available
        if rag_context:
            enhanced_prompt += f"""

## Relevant Athlete Data

The following information from the athlete's history may be relevant to this conversation:

{rag_context}

When providing advice, reference specific data points from above when relevant. For example, mention specific activities, measurements, or logs to make your guidance more personalized and evidence-based."""
        
        return enhanced_prompt
    
    def _get_athlete_profile(self) -> str:
        """
        Get athlete profile information.
        
        Returns:
            Formatted athlete profile string
        """
        # For now, return a placeholder
        # In a full implementation, this would query athlete profile from database
        return """**Name**: Athlete
**Current Plan**: General Fitness
**Primary Goals**: Improve overall fitness and health"""
    
    def _get_active_goals_context(self) -> str:
        """
        Get active goals for context.
        
        Returns:
            Formatted active goals string
        """
        try:
            active_goals = self.goal_service.get_active_goals()
            
            if not active_goals:
                return ""
            
            goal_parts = []
            for i, goal in enumerate(active_goals, 1):
                goal_text = f"{i}. **{goal.goal_type.replace('_', ' ').title()}**: {goal.description}"
                
                if goal.target_value:
                    goal_text += f" (Target: {goal.target_value})"
                
                if goal.target_date:
                    goal_text += f" (By: {goal.target_date.strftime('%Y-%m-%d')})"
                
                goal_parts.append(goal_text)
            
            return "\n".join(goal_parts)
        except Exception as e:
            print(f"[LangChain] Error getting active goals: {e}")
            return ""
    
    def _format_rag_context(self, results: List[Dict[str, Any]]) -> str:
        """
        Format RAG search results for LLM context.
        
        Args:
            results: List of search results from RAG system
        
        Returns:
            Formatted context string
        """
        if not results:
            return ""
        
        context_parts = []
        
        for i, result in enumerate(results, 1):
            record_type = result['record_type']
            text = result['text']
            similarity = result['similarity']
            
            # Format based on record type
            if record_type == 'activity':
                context_parts.append(f"{i}. **Activity**: {text} (relevance: {similarity:.2f})")
            elif record_type == 'metric':
                context_parts.append(f"{i}. **Body Measurement**: {text} (relevance: {similarity:.2f})")
            elif record_type == 'log':
                context_parts.append(f"{i}. **Daily Log**: {text} (relevance: {similarity:.2f})")
            elif record_type == 'evaluation':
                context_parts.append(f"{i}. **Evaluation**: {text} (relevance: {similarity:.2f})")
            else:
                context_parts.append(f"{i}. {text} (relevance: {similarity:.2f})")
        
        return "\n".join(context_parts)

