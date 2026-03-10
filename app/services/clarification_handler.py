"""Clarification Request Handler

Detects low-confidence user intent and generates clarification questions
with specific options to help the user provide more context.

Requirements: 4.1, 4.2, 4.3
"""
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ClarificationHandler:
    """
    Handles clarification requests when user intent is unclear.
    
    Flow:
    1. Detect low-confidence user intent
    2. Generate clarification questions with specific options
    3. Process original request with additional context
    
    Requirements: 4.1, 4.2, 4.3
    """
    
    # Keywords that indicate ambiguous requests
    AMBIGUOUS_KEYWORDS = [
        'plan', 'training', 'workout', 'program', 'schedule',
        'goal', 'target', 'improve', 'better', 'faster',
        'help', 'advice', 'recommend', 'suggest'
    ]
    
    # Minimum context required for confident processing
    MIN_CONTEXT_WORDS = 10
    
    def __init__(self, llm_client: LLMClient):
        """
        Initialize clarification handler.
        
        Args:
            llm_client: LLM client for generating clarification questions
        """
        self.llm_client = llm_client
    
    def needs_clarification(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]]
    ) -> bool:
        """
        Determine if user message needs clarification.
        
        Checks for:
        - Ambiguous keywords without sufficient context
        - Very short messages with action-oriented keywords
        - Requests that could have multiple interpretations
        
        Args:
            user_message: User's message text
            conversation_history: Previous conversation messages
        
        Returns:
            True if clarification is needed, False otherwise
        
        Requirements: 4.1
        """
        message_lower = user_message.lower()
        word_count = len(user_message.split())
        
        # Check for ambiguous keywords
        has_ambiguous_keyword = any(
            keyword in message_lower 
            for keyword in self.AMBIGUOUS_KEYWORDS
        )
        
        # Short messages with ambiguous keywords need clarification
        if has_ambiguous_keyword and word_count < self.MIN_CONTEXT_WORDS:
            logger.info(
                f"Clarification needed: ambiguous keyword with short message",
                extra={
                    "message": user_message,
                    "word_count": word_count
                }
            )
            return True
        
        # Check for very vague requests
        vague_patterns = [
            'help me',
            'what should i',
            'how do i',
            'i want to',
            'i need',
            'can you'
        ]
        
        is_vague = any(pattern in message_lower for pattern in vague_patterns)
        if is_vague and word_count < 8:
            logger.info(
                f"Clarification needed: vague request",
                extra={
                    "message": user_message,
                    "word_count": word_count
                }
            )
            return True
        
        # Check for requests about training plans without specifics
        if 'plan' in message_lower or 'training' in message_lower:
            # Look for specific details
            has_sport = any(
                sport in message_lower 
                for sport in ['run', 'cycle', 'swim', 'triathlon', 'bike']
            )
            has_duration = any(
                word in message_lower 
                for word in ['week', 'month', 'day']
            )
            has_goal = any(
                word in message_lower 
                for word in ['marathon', 'race', '5k', '10k', 'half', 'century', 'ironman']
            )
            
            if not (has_sport or has_duration or has_goal):
                logger.info(
                    f"Clarification needed: training plan request without specifics",
                    extra={"message": user_message}
                )
                return True
        
        return False
    
    async def generate_clarification(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Generate clarification question with specific options.
        
        Uses LLM to create contextual clarification questions that help
        the user provide more specific information.
        
        Args:
            user_message: User's ambiguous message
            conversation_history: Previous conversation messages
        
        Returns:
            Clarification question with specific options
        
        Requirements: 4.2
        """
        # Build prompt for clarification generation
        prompt = self._build_clarification_prompt(user_message, conversation_history)
        
        try:
            # Generate clarification with LLM
            response = await self.llm_client.chat_completion(
                messages=[
                    {
                        'role': 'system',
                        'content': self._get_clarification_system_prompt()
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            clarification = response.get('content', '')
            
            logger.info(
                f"Generated clarification question",
                extra={
                    "original_message": user_message,
                    "clarification_length": len(clarification)
                }
            )
            
            return clarification
            
        except Exception as e:
            logger.error(
                f"Error generating clarification: {str(e)}",
                exc_info=True
            )
            # Return fallback clarification
            return self._generate_fallback_clarification(user_message)
    
    def _build_clarification_prompt(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Build prompt for clarification generation.
        
        Args:
            user_message: User's ambiguous message
            conversation_history: Previous conversation messages
        
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            f"The user said: \"{user_message}\"",
            "\nThis message is ambiguous and needs clarification."
        ]
        
        # Add conversation context if available
        if conversation_history:
            prompt_parts.append("\n\nRecent conversation:")
            for msg in conversation_history[-3:]:  # Last 3 messages
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                prompt_parts.append(f"{role}: {content}")
        
        prompt_parts.append("\n\nGenerate a clarification question that:")
        prompt_parts.append("1. Acknowledges what the user wants")
        prompt_parts.append("2. Asks for specific missing information")
        prompt_parts.append("3. Provides 3-4 concrete options or examples")
        prompt_parts.append("4. Is friendly and encouraging")
        
        return "\n".join(prompt_parts)
    
    def _get_clarification_system_prompt(self) -> str:
        """
        Get system prompt for clarification generation.
        
        Returns:
            System prompt string
        """
        return """You are an expert fitness coach helping athletes clarify their requests.

When a user's request is ambiguous, you generate helpful clarification questions that:
- Show you understand their general intent
- Ask for specific missing details
- Provide concrete options or examples
- Are friendly and encouraging
- Use bullet points for clarity

Examples of good clarification questions:

User: "I need a training plan"
Clarification: "I'd love to help you create a training plan! To make it perfect for you, I need a few more details:

**What sport are you training for?**
- Running (5K, 10K, half marathon, marathon)
- Cycling (road, mountain, gravel)
- Triathlon (sprint, Olympic, half, full)
- Swimming
- Other

**What's your goal?**
- Complete a specific race or event
- Improve fitness and endurance
- Lose weight
- Get faster at a certain distance

**How many weeks do you want the plan to be?**
- 4-8 weeks (short term)
- 8-12 weeks (medium term)
- 12-16 weeks (race preparation)

Let me know and I'll create a personalized plan for you!"

User: "Help me get faster"
Clarification: "Great goal! I can definitely help you improve your speed. To give you the best advice, I need to know:

**What activity do you want to get faster at?**
- Running (what distance?)
- Cycling (road, mountain, track?)
- Swimming (pool, open water?)

**What's your current level?**
- Beginner (just starting out)
- Intermediate (training regularly)
- Advanced (competitive athlete)

**What's your current pace/time?**
For example: "I run 5K in 30 minutes" or "I cycle 20 miles in 90 minutes"

Share these details and I'll create a targeted speed improvement plan!"

Generate similar clarification questions that are specific, helpful, and actionable."""
    
    def _generate_fallback_clarification(self, user_message: str) -> str:
        """
        Generate fallback clarification when LLM is unavailable.
        
        Args:
            user_message: User's ambiguous message
        
        Returns:
            Fallback clarification question
        """
        message_lower = user_message.lower()
        
        # Training plan clarification
        if 'plan' in message_lower or 'training' in message_lower:
            return """I'd love to help you create a training plan! To make it perfect for you, I need a few more details:

**What sport are you training for?**
- Running (5K, 10K, half marathon, marathon)
- Cycling (road, mountain, gravel)
- Triathlon (sprint, Olympic, half, full)
- Swimming
- Other

**What's your goal?**
- Complete a specific race or event
- Improve fitness and endurance
- Lose weight
- Get faster at a certain distance

**How many weeks do you want the plan to be?**
- 4-8 weeks (short term)
- 8-12 weeks (medium term)
- 12-16 weeks (race preparation)

Let me know and I'll create a personalized plan for you!"""
        
        # Goal clarification
        if 'goal' in message_lower:
            return """I'd be happy to help you set a fitness goal! To make it specific and achievable, tell me:

**What type of goal are you thinking about?**
- Performance (e.g., run a faster 5K, complete a century ride)
- Weight management (lose or gain weight)
- Endurance (build stamina, go longer distances)
- Strength (get stronger, build muscle)
- General fitness (feel better, more energy)

**What's your timeframe?**
- Short term (1-3 months)
- Medium term (3-6 months)
- Long term (6-12 months)

**Do you have a specific target?**
For example: "Run a sub-4 hour marathon" or "Lose 10 pounds"

Share these details and I'll help you create a clear, actionable goal!"""
        
        # Improvement clarification
        if any(word in message_lower for word in ['improve', 'better', 'faster']):
            return """I can help you improve! To give you the best advice, I need to know:

**What do you want to improve?**
- Speed/pace
- Endurance/distance
- Strength/power
- Technique/form
- Recovery/consistency

**What activity?**
- Running
- Cycling
- Swimming
- Triathlon
- Other

**What's your current level?**
- Beginner (just starting)
- Intermediate (training regularly)
- Advanced (competitive)

Tell me more and I'll create a targeted improvement plan!"""
        
        # Generic clarification
        return """I'd love to help! To give you the best advice, could you tell me more about:

**What you're trying to achieve?**
- Create a training plan
- Set a fitness goal
- Improve performance
- Analyze your training
- Get nutrition advice

**Your sport or activity?**
- Running
- Cycling
- Swimming
- Triathlon
- Other

**Your experience level?**
- Beginner
- Intermediate
- Advanced

Share more details and I'll provide personalized guidance!"""
    
    async def process_with_clarification(
        self,
        original_message: str,
        clarification_response: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Process original request with additional clarification context.
        
        Combines the original ambiguous message with the user's clarification
        response to create a complete, unambiguous request.
        
        Args:
            original_message: User's original ambiguous message
            clarification_response: User's response to clarification question
            conversation_history: Previous conversation messages
        
        Returns:
            Combined context for processing
        
        Requirements: 4.3
        """
        # Combine original message with clarification
        combined_context = f"""Original request: {original_message}

Additional details provided: {clarification_response}

Based on this information, please provide a complete response to the user's request."""
        
        logger.info(
            f"Processing with clarification",
            extra={
                "original_message": original_message,
                "clarification_response": clarification_response
            }
        )
        
        return combined_context
