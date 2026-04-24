"""LM Studio Chat Service with Tool Calling

Uses LM Studio's native API format (/api/v1/chat) instead of OpenAI-compatible format.
"""
import asyncio
import json
import logging
import httpx
from typing import List, Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session

from app.services.goal_service import GoalService
from app.config import get_settings

logger = logging.getLogger(__name__)


class LMStudioChatService:
    """
    LM Studio-specific chat service with tool calling.
    
    Uses LM Studio's native /api/v1/chat endpoint.
    """
    
    def __init__(self, db: Session):
        """
        Initialize LM Studio chat service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.goal_service = GoalService(db)
        self.settings = get_settings()
        
        # LM Studio uses /api/v1/chat endpoint
        self.base_url = self.settings.llm_base_url.rstrip('/')
        self.endpoint = f"{self.base_url}/api/v1/chat"
        self.model = self.settings.OLLAMA_MODEL
        
        logger.debug("Initialized: endpoint=%s model=%s", self.endpoint, self.model)
    
    async def get_chat_response(
        self,
        messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Get chat response with tool calling.
        
        Args:
            messages: Conversation history
        
        Returns:
            Response dict
        """
        try:
            # Load system prompt
            system_prompt = self._load_system_prompt()
            
            # Build the input from messages
            # LM Studio expects a single "input" field with the latest user message
            user_message = messages[-1]['content'] if messages else ""
            
            # Build conversation context from history
            context = ""
            if len(messages) > 1:
                for msg in messages[:-1]:
                    role = msg['role'].capitalize()
                    context += f"{role}: {msg['content']}\n\n"
            
            # Combine system prompt with context
            full_system_prompt = system_prompt
            if context:
                full_system_prompt += f"\n\nConversation history:\n{context}"
            
            logger.debug("Sending request to %s: %.100s...", self.endpoint, user_message)
            
            # Call LM Studio API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.endpoint,
                    json={
                        "model": self.model,
                        "system_prompt": full_system_prompt,
                        "input": user_message,
                        "temperature": 0.7,
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"LM Studio returned status {response.status_code}: {response.text}")
                
                data = response.json()
                
                # Extract the response
                # LM Studio returns: {"model_instance_id": "...", "output": [...]}
                output = data.get('output', [])
                
                # Find the message content
                content = ""
                for item in output:
                    if item.get('type') == 'message':
                        content = item.get('content', '')
                        break
                
                logger.debug("Response received: %.200s...", content)

                if self._should_save_goal(content, user_message):
                    logger.debug("Detected goal-setting intent, extracting goal details")
                    goal_data = self._extract_goal_from_response(content, user_message)

                    if goal_data:
                        logger.debug("Extracted goal data: %s", goal_data)
                        try:
                            result = self.goal_service.save_goal(**goal_data)
                            if result['success']:
                                content += f"\n\n✅ Goal saved! ID: {result['goal_id']}"
                                logger.info("Goal saved: %s", result['goal_id'])
                            else:
                                content += f"\n\n❌ Failed to save goal: {result.get('message', 'Unknown error')}"
                        except Exception as e:
                            logger.error("Error saving goal: %s", e)
                            content += f"\n\n❌ Error saving goal: {str(e)}"
                
                return {
                    'content': content,
                    'messages': messages
                }
            
        except Exception as e:
            logger.error("LMStudio error: %s", e, exc_info=True)
            
            return {
                'content': f"I encountered an error: {str(e)}. Please make sure LM Studio is running.",
                'messages': messages,
                'error': str(e)
            }
    
    def _should_save_goal(self, response: str, user_message: str) -> bool:
        """Check if we should attempt to save a goal based on the conversation."""
        response_lower = response.lower()
        user_lower = user_message.lower()
        
        # Check if user provided goal information
        has_goal_info = any(keyword in user_lower for keyword in [
            'want to', 'goal', 'lose weight', 'gain weight', 'get stronger',
            'improve', 'train for', 'prepare for'
        ])
        
        # Check if response indicates readiness to save
        ready_to_save = any(phrase in response_lower for phrase in [
            'save this goal', 'save the goal', 'let me save', "i'll save",
            'goal saved', 'set up your goal', 'create this goal'
        ])
        
        return has_goal_info and ready_to_save
    
    def _extract_goal_from_response(self, response: str, user_message: str) -> Dict[str, Any]:
        """
        Extract goal parameters from the conversation.
        
        This is a simple heuristic-based extraction. In a production system,
        you might want to use a more sophisticated NLP approach or ask the LLM
        to output structured JSON.
        """
        import re
        from datetime import datetime, timedelta
        
        goal_data = {}
        user_lower = user_message.lower()
        
        # Determine goal type
        if 'lose weight' in user_lower or 'weight loss' in user_lower:
            goal_data['goal_type'] = 'weight_loss'
        elif 'gain weight' in user_lower or 'weight gain' in user_lower:
            goal_data['goal_type'] = 'weight_gain'
        elif 'performance' in user_lower or 'faster' in user_lower or 'race' in user_lower:
            goal_data['goal_type'] = 'performance'
        elif 'endurance' in user_lower or 'distance' in user_lower:
            goal_data['goal_type'] = 'endurance'
        elif 'strength' in user_lower or 'stronger' in user_lower:
            goal_data['goal_type'] = 'strength'
        else:
            goal_data['goal_type'] = 'custom'
        
        # Extract target weight (if applicable)
        weight_match = re.search(r'(\d+(?:\.\d+)?)\s*kg', user_message, re.IGNORECASE)
        if weight_match and goal_data['goal_type'] in ['weight_loss', 'weight_gain']:
            goal_data['target_value'] = float(weight_match.group(1))
        
        # Extract target date
        # Look for dates like "May 30", "2026-05-30", etc.
        date_patterns = [
            r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?',  # "May 30"
            r'(\d{4})-(\d{2})-(\d{2})',  # "2026-05-30"
            r'by\s+(\w+)\s+(\d{1,2})',  # "by May 30"
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, user_message, re.IGNORECASE)
            if date_match:
                try:
                    # Try to parse the date
                    # This is simplified - in production, use a proper date parser
                    if len(date_match.groups()) == 2:
                        month_str, day_str = date_match.groups()
                        # Assume current year or next year
                        year = datetime.now().year
                        month_map = {
                            'january': 1, 'february': 2, 'march': 3, 'april': 4,
                            'may': 5, 'june': 6, 'july': 7, 'august': 8,
                            'september': 9, 'october': 10, 'november': 11, 'december': 12
                        }
                        month = month_map.get(month_str.lower(), datetime.now().month)
                        day = int(day_str)
                        target_date = datetime(year, month, day).date()
                        
                        # If date is in the past, assume next year
                        if target_date < datetime.now().date():
                            target_date = datetime(year + 1, month, day).date()
                        
                        goal_data['target_date'] = target_date.strftime('%Y-%m-%d')
                        break
                except:
                    pass
        
        # Create description from user message
        goal_data['description'] = user_message[:500]  # Limit to 500 chars
        
        # Only return if we have at least goal_type and description
        if 'goal_type' in goal_data and 'description' in goal_data:
            return goal_data
        
        return None
    
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
    
    def _load_system_prompt(self) -> str:
        """Load system prompt."""
        try:
            with open('app/prompts/goal_setting_prompt.txt', 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return """You are an expert fitness coach. When athletes want to set goals, gather information and help them create clear, achievable goals."""
