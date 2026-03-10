"""Chat Message Handler with Multi-Step Tool Orchestration

Implements the complete chat flow with:
- Two-layer RAG context retrieval (Active Session Buffer + Vector Store)
- Multi-step tool orchestration with sequential execution
- Tool result passing between calls
- Performance monitoring (p95 latency < 3 seconds)

Requirements: 3.1, 3.2, 3.3, 3.4, 17.1
"""
import time
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage
from app.services.rag_engine import RAGEngine
from app.services.llm_client import LLMClient
from app.services.chat_tools import execute_tool, get_tool_definitions

logger = logging.getLogger(__name__)


class ChatMessageHandler:
    """
    Handles chat messages with RAG context retrieval and tool orchestration.
    
    Flow:
    1. Retrieve context from active buffer and vector store
    2. Generate initial LLM response with tool definitions
    3. Execute tools sequentially when requested
    4. Pass tool results to subsequent tool calls
    5. Generate final response incorporating all tool results
    
    Performance target: p95 latency < 3 seconds (Requirement 17.1)
    """
    
    def __init__(
        self,
        db: Session,
        rag_engine: RAGEngine,
        llm_client: LLMClient,
        user_id: int,
        session_id: int
    ):
        """
        Initialize chat message handler.
        
        Args:
            db: SQLAlchemy database session
            rag_engine: RAG engine for context retrieval
            llm_client: LLM client for response generation
            user_id: User ID for scoping
            session_id: Current chat session ID
        """
        self.db = db
        self.rag_engine = rag_engine
        self.llm_client = llm_client
        self.user_id = user_id
        self.session_id = session_id
        
        # Active session buffer (in-memory)
        self.active_session_messages: List[ChatMessage] = []
    
    async def handle_message(
        self,
        user_message: str,
        max_tool_iterations: int = 5
    ) -> Dict[str, Any]:
        """
        Handle a chat message with full RAG and tool orchestration.
        
        Args:
            user_message: User's message text
            max_tool_iterations: Maximum tool calling iterations
        
        Returns:
            Response dict with:
                - content: Final response text
                - tool_calls_made: Number of tool calls executed
                - latency_ms: Total processing time
                - context_retrieved: Whether context was retrieved
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 17.1
        """
        start_time = time.time()
        
        try:
            # Step 1: Retrieve context from both layers (Requirement 3.1)
            context = await self._retrieve_context(user_message)
            
            # Step 2: Build conversation with context
            conversation = self._build_conversation(user_message, context)
            
            # Step 3: Execute multi-step tool orchestration (Requirements 3.2, 3.3, 3.4)
            response = await self._orchestrate_tools(conversation, max_tool_iterations)
            
            # Step 4: Store messages in active session buffer
            self._update_active_buffer(user_message, response['content'])
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Log performance (Requirement 17.1)
            logger.info(
                f"Chat message handled in {latency_ms:.0f}ms",
                extra={
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "latency_ms": latency_ms,
                    "tool_calls": response.get('tool_calls_made', 0),
                    "iterations": response.get('iterations', 0)
                }
            )
            
            # Warn if latency exceeds target
            if latency_ms > 3000:
                logger.warning(
                    f"Chat latency exceeded 3s target: {latency_ms:.0f}ms",
                    extra={
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                        "latency_ms": latency_ms
                    }
                )
            
            return {
                'content': response['content'],
                'tool_calls_made': response.get('tool_calls_made', 0),
                'iterations': response.get('iterations', 0),
                'latency_ms': latency_ms,
                'context_retrieved': bool(context)
            }
            
        except Exception as e:
            logger.error(
                f"Error handling chat message: {str(e)}",
                extra={
                    "user_id": self.user_id,
                    "session_id": self.session_id
                },
                exc_info=True
            )
            raise
    
    async def _retrieve_context(self, query: str) -> str:
        """
        Retrieve context from active buffer and vector store.
        
        Args:
            query: User's message
        
        Returns:
            Formatted context string
        
        Requirements: 1.1, 1.2, 1.3, 17.2
        """
        try:
            context = self.rag_engine.retrieve_context(
                query=query,
                user_id=self.user_id,
                active_session_messages=self.active_session_messages,
                top_k=5
            )
            return context
        except Exception as e:
            logger.error(
                f"Error retrieving context: {str(e)}",
                extra={"user_id": self.user_id, "session_id": self.session_id},
                exc_info=True
            )
            # Return empty context on error
            return ""
    
    def _build_conversation(self, user_message: str, context: str) -> List[Dict[str, str]]:
        """
        Build conversation messages with context.
        
        Args:
            user_message: User's message
            context: Retrieved context from RAG
        
        Returns:
            List of conversation messages
        """
        messages = []
        
        # System prompt with context
        system_prompt = self._get_system_prompt()
        if context:
            system_prompt += f"\n\n## Retrieved Context\n{context}"
        
        messages.append({
            'role': 'system',
            'content': system_prompt
        })
        
        # Add active session messages (last 10 for token efficiency)
        for msg in self.active_session_messages[-10:]:
            messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        # Add current user message
        messages.append({
            'role': 'user',
            'content': user_message
        })
        
        return messages
    
    async def _orchestrate_tools(
        self,
        conversation: List[Dict[str, str]],
        max_iterations: int
    ) -> Dict[str, Any]:
        """
        Execute multi-step tool orchestration.
        
        Handles:
        - Sequential tool execution
        - Passing tool results to subsequent calls
        - Final response generation with all tool results
        
        Args:
            conversation: Initial conversation messages
            max_iterations: Maximum tool calling iterations
        
        Returns:
            Response dict with content and metadata
        
        Requirements: 3.1, 3.2, 3.3, 3.4
        """
        tool_definitions = get_tool_definitions()
        tool_calls_made = 0
        
        for iteration in range(max_iterations):
            # Generate LLM response with tool definitions
            response = await self.llm_client.chat_completion(
                messages=conversation,
                tools=tool_definitions if tool_definitions else None
            )
            
            # Add assistant response to conversation
            assistant_message = {
                'role': 'assistant',
                'content': response.get('content', '')
            }
            
            if 'tool_calls' in response:
                assistant_message['tool_calls'] = response['tool_calls']
            
            conversation.append(assistant_message)
            
            # Check if LLM wants to call tools
            if 'tool_calls' not in response or not response['tool_calls']:
                # No tool calls, return final response (Requirement 3.4)
                return {
                    'content': response['content'],
                    'iterations': iteration + 1,
                    'tool_calls_made': tool_calls_made
                }
            
            # Execute tools sequentially (Requirement 3.1)
            for tool_call in response['tool_calls']:
                tool_name = tool_call['function']['name']
                
                # Parse arguments
                import json
                try:
                    arguments = json.loads(tool_call['function']['arguments'])
                except json.JSONDecodeError:
                    arguments = {}
                
                logger.info(
                    f"Executing tool: {tool_name}",
                    extra={
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                        "tool_name": tool_name,
                        "iteration": iteration + 1
                    }
                )
                
                # Execute tool with user_id scoping (Requirement 3.2)
                try:
                    tool_result = await execute_tool(
                        tool_name=tool_name,
                        parameters=arguments,
                        user_id=self.user_id,
                        db=self.db
                    )
                    tool_calls_made += 1
                except Exception as e:
                    logger.error(
                        f"Tool execution failed: {tool_name}",
                        extra={
                            "user_id": self.user_id,
                            "session_id": self.session_id,
                            "tool_name": tool_name,
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    tool_result = {
                        'success': False,
                        'error': str(e)
                    }
                
                # Add tool result to conversation (Requirement 3.3)
                # This allows subsequent tool calls to use previous results
                conversation.append({
                    'role': 'tool',
                    'tool_call_id': tool_call['id'],
                    'name': tool_name,
                    'content': json.dumps(tool_result)
                })
        
        # Max iterations reached
        logger.warning(
            f"Max tool iterations reached: {max_iterations}",
            extra={
                "user_id": self.user_id,
                "session_id": self.session_id,
                "tool_calls_made": tool_calls_made
            }
        )
        
        return {
            'content': 'I apologize, but I need to simplify my approach. Could you rephrase your request?',
            'iterations': max_iterations,
            'tool_calls_made': tool_calls_made,
            'max_iterations_reached': True
        }
    
    def _update_active_buffer(self, user_message: str, assistant_response: str) -> None:
        """
        Update active session buffer with new messages.
        
        Args:
            user_message: User's message
            assistant_response: Assistant's response
        """
        # Create message objects (not persisted yet)
        user_msg = ChatMessage(
            session_id=self.session_id,
            role='user',
            content=user_message
        )
        
        assistant_msg = ChatMessage(
            session_id=self.session_id,
            role='assistant',
            content=assistant_response
        )
        
        # Add to active buffer
        self.active_session_messages.append(user_msg)
        self.active_session_messages.append(assistant_msg)
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt for AI coach.
        
        Returns:
            System prompt string
        """
        return """You are an expert fitness coach and training advisor. Your role is to help athletes achieve their fitness goals through personalized guidance, motivation, and evidence-based advice.

## Your Expertise:
- **Training**: Workout programming, periodization, recovery strategies, training plan generation
- **Nutrition**: Macro/micro nutrients, meal timing, supplementation
- **Performance**: Race strategy, pacing, mental preparation
- **Recovery**: Sleep optimization, injury prevention, active recovery
- **Goal Setting**: SMART goals, progress tracking, motivation
- **Data Analysis**: Activity analysis, trend identification, performance insights

## Available Tools:
You have access to tools that allow you to:
- Save and retrieve athlete goals
- Access recent training activities from Strava
- Get weekly training metrics and trends
- Generate and save personalized training plans
- Search the web for current fitness information

## Your Approach:
- Use tools to gather athlete data before making recommendations
- Ask clarifying questions when intent is unclear
- Provide specific, actionable advice based on actual data
- Present training plans for review before saving
- Adapt recommendations to individual needs and current fitness level
- Celebrate progress and milestones

## Communication Style:
- Friendly and conversational
- Use emojis occasionally for warmth (🏃, 💪, 🎯, etc.)
- Break down complex topics into digestible points
- Use bullet points and formatting for clarity
- Be concise but thorough

## Important Guidelines:
- Always retrieve athlete data (activities, metrics, goals) before generating training plans
- Present generated training plans to the athlete for review and confirmation
- Wait for explicit confirmation before saving plans
- If the athlete requests modifications, regenerate the plan with the requested changes
- Base training volume on recent activity history to ensure progressive overload"""
    
    def get_active_session_messages(self) -> List[ChatMessage]:
        """
        Get current active session messages.
        
        Returns:
            List of ChatMessage objects in active buffer
        """
        return self.active_session_messages.copy()
    
    def load_session_messages(self, messages: List[ChatMessage]) -> None:
        """
        Load existing session messages into active buffer.
        
        Args:
            messages: List of ChatMessage objects to load
        """
        self.active_session_messages = messages.copy()
    
    def clear_active_buffer(self) -> None:
        """Clear the active session buffer."""
        self.active_session_messages.clear()
    
    async def persist_session(self, eval_score: Optional[float] = None) -> None:
        """
        Persist active session to vector store.
        
        Args:
            eval_score: Optional evaluation score for the session
        
        Requirements: 1.4, 1.5
        """
        if not self.active_session_messages:
            logger.info(
                "No messages to persist",
                extra={"user_id": self.user_id, "session_id": self.session_id}
            )
            return
        
        try:
            self.rag_engine.persist_session(
                user_id=self.user_id,
                session_id=self.session_id,
                messages=self.active_session_messages,
                eval_score=eval_score
            )
            
            logger.info(
                f"Persisted {len(self.active_session_messages)} messages to vector store",
                extra={
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "message_count": len(self.active_session_messages)
                }
            )
        except Exception as e:
            logger.error(
                f"Error persisting session: {str(e)}",
                extra={"user_id": self.user_id, "session_id": self.session_id},
                exc_info=True
            )
            raise
