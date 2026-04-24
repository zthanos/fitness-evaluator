"""Chat Service

Handles AI coach chat functionality with LLM integration and tool calling.
Supports streaming responses and goal setting through conversation.
"""
import asyncio
import logging
from typing import List, Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
from app.services.llm_client import LLMClient
from app.services.goal_service import GoalService


class ChatService:
    """
    Service for managing AI coach chat with LLM integration.
    
    Provides:
    - Streaming chat responses
    - Tool calling for goal setting
    - Conversation context management
    """
    
    def __init__(self, db: Session):
        """
        Initialize ChatService.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.llm_client = LLMClient()
        self.goal_service = GoalService(db)
        
        # Register goal setting tool
        self._register_tools()
    
    def _register_tools(self):
        """Register available tools for LLM function calling."""
        # Register goal setting tool
        tool_def = GoalService.get_tool_definition()
        self.llm_client.register_tool(
            name='save_athlete_goal',
            handler=self.goal_service.save_goal,
            definition=tool_def
        )
    
    async def get_chat_response(
        self,
        messages: List[Dict[str, str]],
        use_goal_setting: bool = True
    ) -> Dict[str, Any]:
        """
        Get a chat response from the LLM with tool calling support.
        
        Args:
            messages: Conversation history
            use_goal_setting: Whether to enable goal setting tool
        
        Returns:
            Response dict with content and metadata
        """
        # Add system prompt for coach persona
        system_prompt = self._get_system_prompt(use_goal_setting)
        
        full_messages = [
            {'role': 'system', 'content': system_prompt}
        ] + messages
        
        try:
            # Use chat_with_tools for automatic tool execution
            logger.debug("Sending %d messages to LLM (tools: %s)", len(full_messages), list(self.llm_client.tools.keys()))
            response = await self.llm_client.chat_with_tools(full_messages)
            logger.debug("Response: %d iterations, %d chars", response.get('iterations', 0), len(response.get('content', '')))
            return response
        except Exception as e:
            logger.error("LLM error: %s", e)
            import traceback
            traceback.print_exc()
            # Fall back to mock response
            return {
                'content': self._generate_fallback_response(messages[-1]['content'] if messages else ''),
                'messages': full_messages,
                'iterations': 0,
                'fallback': True
            }
    
    async def stream_chat_response(
        self,
        messages: List[Dict[str, str]],
        use_goal_setting: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response from the LLM.
        
        Args:
            messages: Conversation history
            use_goal_setting: Whether to enable goal setting tool
        
        Yields:
            Response chunks as they're generated
        """
        try:
            # Get response (with fallback if LLM unavailable)
            response = await self.get_chat_response(messages, use_goal_setting)
            
            content = response.get('content', '')
            
            # Simulate streaming by yielding words
            words = content.split(' ')
            for i, word in enumerate(words):
                if i > 0:
                    yield ' '
                yield word
                # Small delay to simulate streaming
                await asyncio.sleep(0.02)
        except Exception as e:
            # If everything fails, yield error message
            error_msg = f"I'm having trouble connecting right now. Please check that the LLM server is running. Error: {str(e)}"
            words = error_msg.split(' ')
            for i, word in enumerate(words):
                if i > 0:
                    yield ' '
                yield word
                await asyncio.sleep(0.02)
    
    def _get_system_prompt(self, include_goal_setting: bool = True) -> str:
        """
        Get the system prompt for the AI coach.
        
        Args:
            include_goal_setting: Whether to include goal setting instructions
        
        Returns:
            System prompt string
        """
        if include_goal_setting:
            # Use dedicated goal setting prompt
            try:
                with open('app/prompts/goal_setting_prompt.txt', 'r') as f:
                    return f.read()
            except FileNotFoundError:
                logger.warning("goal_setting_prompt.txt not found, using fallback")
        
        # Fallback to base prompt
        base_prompt = """You are an expert fitness coach and nutrition advisor. Your role is to help athletes achieve their fitness goals through personalized guidance, motivation, and evidence-based advice.

## Your Expertise:
- **Training**: Workout programming, periodization, recovery strategies
- **Nutrition**: Macro/micro nutrients, meal timing, supplementation
- **Performance**: Race strategy, pacing, mental preparation
- **Recovery**: Sleep optimization, injury prevention, active recovery
- **Goal Setting**: SMART goals, progress tracking, motivation

## Your Approach:
- Be supportive, encouraging, and motivating
- Ask clarifying questions to understand context
- Provide specific, actionable advice
- Use data and evidence when available
- Adapt recommendations to individual needs
- Celebrate progress and milestones

## Communication Style:
- Friendly and conversational
- Use emojis occasionally for warmth (🏃, 💪, 🎯, etc.)
- Break down complex topics into digestible points
- Use bullet points and formatting for clarity
- Be concise but thorough"""
        
        return base_prompt
    
    def _generate_fallback_response(self, user_message: str) -> str:
        """
        Generate a fallback response when LLM is unavailable.
        
        Args:
            user_message: The user's message
        
        Returns:
            Fallback response string
        """
        lower_message = user_message.lower()
        
        if 'goal' in lower_message:
            return """Great! I'd love to help you set a fitness goal. Let me ask you a few questions to make sure we create a goal that's specific, measurable, and achievable.

**First, what type of goal are you thinking about?**
- Weight loss
- Weight gain  
- Performance improvement (e.g., faster 5K time)
- Building endurance
- Getting stronger
- Something else

Tell me what you have in mind!

_Note: I'm currently running in offline mode. For full AI-powered responses, please ensure the LLM server is running._"""
        
        if 'progress' in lower_message or 'training' in lower_message:
            return """I'd be happy to review your progress! 📊

To provide personalized insights, I need access to your activity data. Once connected, I can analyze:
- Your recent training volume and intensity
- Pace and performance trends
- Recovery patterns
- Recommendations for improvement

_Note: I'm currently running in offline mode. For full AI-powered responses, please ensure the LLM server is running._"""
        
        if 'nutrition' in lower_message or 'diet' in lower_message:
            return """Let's talk nutrition! 🥗

**General Principles:**
1. **Protein**: Aim for 1.6-2.2g per kg of body weight daily
2. **Carbs**: Your primary fuel source - don't fear them!
3. **Fats**: Essential for hormones - aim for 0.8-1g per kg
4. **Hydration**: Drink 30-40ml per kg of body weight

What specific nutrition questions do you have?

_Note: I'm currently running in offline mode. For full AI-powered responses, please ensure the LLM server is running._"""
        
        # Default response
        return """I'm your AI fitness coach! I can help with:

- **Goal Setting**: Define and track fitness goals
- **Training Plans**: Create customized workout programs
- **Nutrition Advice**: Guidance on diet and macros
- **Progress Analysis**: Review training data and suggest improvements
- **Recovery**: Advise on rest, sleep, and injury prevention

What would you like to focus on today?

_Note: I'm currently running in offline mode. For full AI-powered responses, please ensure the LLM server (Ollama/LM Studio) is running at the configured endpoint._"""
