# app/services/llm_client.py
import httpx
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from app.config import get_settings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

def normalize_base_url(base_url: str) -> str:
    """
    Normalize the base URL by:
    1. Stripping trailing slashes (including multiple)
    2. Removing /api suffix if present

    Examples:
        "http://ollama:11434/api" -> "http://ollama:11434"
        "http://ollama:11434/api/" -> "http://ollama:11434"
        "http://ollama:11434/api///" -> "http://ollama:11434"
        "http://localhost:1234" -> "http://localhost:1234"
        "http://localhost:1234/" -> "http://localhost:1234"
    """
    # Strip all trailing slashes
    normalized = base_url.rstrip('/')

    # Remove /api suffix if present
    if normalized.endswith('/api'):
        normalized = normalized[:-4]  # Remove the last 4 characters ("/api")

    return normalized


def construct_openai_endpoint(base_url: str) -> str:
    """
    Construct the OpenAI-compatible endpoint URL.

    Takes a base URL (potentially with /api suffix or trailing slashes)
    and returns the correct OpenAI-compatible endpoint with /v1/chat/completions.

    Args:
        base_url: The base URL (e.g., "http://ollama:11434/api" or "http://localhost:1234")

    Returns:
        The full OpenAI-compatible endpoint URL (e.g., "http://ollama:11434/v1/chat/completions")

    Examples:
        "http://ollama:11434/api" -> "http://ollama:11434/v1/chat/completions"
        "http://ollama:11434/api/" -> "http://ollama:11434/v1/chat/completions"
        "http://localhost:1234" -> "http://localhost:1234/v1/chat/completions"
    """
    normalized = normalize_base_url(base_url)
    return f"{normalized}/v1/chat/completions"


class LLMClient:
    """
    Enhanced LLM Client with LangChain integration.
    
    Supports both Ollama and LM Studio (OpenAI-compatible) backends through LangChain.
    Handles tool execution, conversation management, and streaming responses.
    Implements retry logic with exponential backoff.
    
    Requirements: 21.1, 21.2, 21.3, 21.8, 21.10
    """
    
    def __init__(self):
        """
        Initialize LLM client with settings.
        
        Logs all initialization parameters for debugging (Requirement 21.10).
        """
        self.settings = get_settings()
        self.tools: Dict[str, Callable] = {}
        self.endpoint_url = construct_openai_endpoint(self.settings.llm_base_url)
        self.model_name = (
            self.settings.OLLAMA_MODEL 
            if self.settings.is_ollama 
            else self.settings.LM_STUDIO_MODEL
        )
        
        logger.debug("Initializing: backend=%s endpoint=%s model=%s", self.settings.LLM_TYPE, self.endpoint_url, self.model_name)
    
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """
        Generate a response from the LLM using LangChain.
        
        Implements retry logic with exponential backoff (max 3 retries).
        Handles connection errors and timeouts gracefully.
        
        Requirements: 21.1, 21.8, 29.7
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (default 0.7 for chat)
            max_tokens: Maximum tokens in response (default 500 for chat flow)
        
        Returns:
            Generated response text
        
        Raises:
            httpx.HTTPError: After 3 failed retry attempts
        """
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        
        logger.debug("generate_response: temperature=%s max_tokens=%d", temperature, max_tokens)
        
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("user", "{prompt}"))
        
        prompt_template = ChatPromptTemplate.from_messages(messages)
        
        # Initialize LangChain ChatOpenAI
        llm = ChatOpenAI(
            base_url=self.endpoint_url.replace('/v1/chat/completions', ''),
            model=self.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key="not-needed"  # Required by LangChain but not used by Ollama/LM Studio
        )
        
        chain = prompt_template | llm
        
        # Retry logic with exponential backoff (Requirement 21.8)
        for attempt in range(3):
            try:
                logger.debug("Attempt %d/3", attempt + 1)
                result = await chain.ainvoke({"prompt": prompt})
                if hasattr(result, 'content'):
                    return result.content
                return str(result)

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning("Connection error on attempt %d: %s", attempt + 1, e)
                if attempt == 2:
                    logger.error("All retry attempts failed")
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error("LLM error: %s", e)
                raise
    
    async def stream_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from the LLM using LangChain streaming capabilities.
        
        Implements retry logic with exponential backoff (max 3 retries).
        Handles connection errors and timeouts gracefully.
        
        Requirements: 21.1, 21.8, 29.7
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (default 0.7 for chat)
            max_tokens: Maximum tokens in response (default 500 for chat flow)
        
        Yields:
            Response chunks as they arrive
        
        Raises:
            httpx.HTTPError: After 3 failed retry attempts
        """
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        from typing import AsyncGenerator
        
        logger.debug("stream_response: temperature=%s max_tokens=%d", temperature, max_tokens)
        
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("user", "{prompt}"))
        
        prompt_template = ChatPromptTemplate.from_messages(messages)
        
        # Initialize LangChain ChatOpenAI
        llm = ChatOpenAI(
            base_url=self.endpoint_url.replace('/v1/chat/completions', ''),
            model=self.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key="not-needed"
        )
        
        chain = prompt_template | llm
        
        # Retry logic with exponential backoff (Requirement 21.8)
        for attempt in range(3):
            try:
                logger.debug("Stream attempt %d/3", attempt + 1)
                async for chunk in chain.astream({"prompt": prompt}):
                    if hasattr(chunk, 'content'):
                        yield chunk.content
                    else:
                        yield str(chunk)
                break

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning("Connection error on stream attempt %d: %s", attempt + 1, e)
                if attempt == 2:
                    logger.error("All stream retry attempts failed")
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error("Stream error: %s", e)
                raise
    
    def _build_prompt(
        self,
        user_message: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        athlete_profile: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build a comprehensive prompt with context and history using LangChain formatting.
        
        Requirements: 29.1, 29.2, 29.3, 29.4, 29.7, 29.8
        
        Args:
            user_message: The current user message
            context: RAG-retrieved context (formatted)
            history: Conversation history (last 10 messages)
            athlete_profile: Athlete profile information (name, goals, current plan)
        
        Returns:
            Formatted prompt string with all context
        """
        from langchain_core.prompts import ChatPromptTemplate
        
        # Build system prompt components
        system_parts = []
        
        # Base coach persona (Requirement 29.1)
        system_parts.append("""You are an expert fitness coach with deep knowledge of training, nutrition, and body composition.
Your role is to provide personalized, evidence-based coaching to athletes.

## Your Coaching Style
- **Knowledgeable**: You understand exercise physiology, nutrition science, and training principles
- **Supportive**: You encourage athletes and celebrate their progress
- **Evidence-Based**: You always cite specific data points from the athlete's history when making recommendations
- **Actionable**: You provide concrete, specific advice that athletes can implement immediately""")
        
        # Add athlete profile if available (Requirement 29.3)
        if athlete_profile:
            profile_parts = ["## Athlete Profile"]
            if athlete_profile.get('name'):
                profile_parts.append(f"**Name**: {athlete_profile['name']}")
            if athlete_profile.get('goals'):
                profile_parts.append(f"**Goals**: {athlete_profile['goals']}")
            if athlete_profile.get('current_plan'):
                profile_parts.append(f"**Current Plan**: {athlete_profile['current_plan']}")
            
            system_parts.append("\n".join(profile_parts))
        
        # Add RAG context if available (Requirement 29.2, 29.4)
        if context:
            system_parts.append(f"""## Relevant Athlete Data

The following information from the athlete's history may be relevant to this conversation:

{context}

**IMPORTANT**: When providing advice, reference specific data points from above. For example, mention specific activities, measurements, or logs to make your guidance more personalized and evidence-based.""")
        
        system_prompt = "\n\n".join(system_parts)
        
        # Build message list with history (Requirement 29.8)
        messages = [("system", system_prompt)]
        
        # Add conversation history (last 10 messages)
        if history:
            for msg in history[-10:]:  # Last 10 messages for context continuity
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role == 'user':
                    messages.append(("user", content))
                elif role == 'assistant':
                    messages.append(("assistant", content))
        
        # Add current user message
        messages.append(("user", user_message))
        
        # Create prompt template
        prompt_template = ChatPromptTemplate.from_messages(messages)
        
        # Format and return
        return prompt_template.format()
    
    def register_tool(self, name: str, handler: Callable, definition: Dict[str, Any]):
        """
        Register a tool for LLM function calling.
        
        Args:
            name: Tool name (must match function name in definition)
            handler: Callable that executes the tool
            definition: Tool definition dict compatible with OpenAI function calling
        """
        self.tools[name] = {
            'handler': handler,
            'definition': definition
        }
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a registered tool.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments from LLM
        
        Returns:
            Tool execution result
        
        Raises:
            ValueError: If tool is not registered
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' is not registered")
        
        handler = self.tools[tool_name]['handler']
        
        try:
            result = handler(**arguments)
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"Tool execution failed: {str(e)}"
            }
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Send a chat completion request with optional tool calling.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)
            response_format: Optional response format (e.g., {"type": "json_object"})
        
        Returns:
            Response dict with 'content' and optional 'tool_calls'
        
        Raises:
            httpx.HTTPError: On connection or HTTP errors
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        if response_format:
            payload["response_format"] = response_format
        
        if tools:
            payload["tools"] = tools
        
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(self.endpoint_url, json=payload)
                    
                    # Log the error response for debugging
                    if response.status_code == 400:
                        error_detail = response.text
                        logger.error("400 Bad Request from %s: %s", self.backend, error_detail)
                        logger.debug("Request payload: %s", json.dumps(payload, indent=2))
                    
                    response.raise_for_status()
                    
                    data = response.json()
                    choice = data["choices"][0]
                    message = choice["message"]
                    
                    result = {
                        'content': message.get('content'),
                        'role': message.get('role', 'assistant')
                    }
                    
                    # Check for tool calls
                    if 'tool_calls' in message:
                        result['tool_calls'] = message['tool_calls']
                    
                    return result
                    
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
    
    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """
        Chat with automatic tool execution.

        Handles the full tool calling loop:
        1. Send messages to LLM
        2. If LLM calls tools, execute them
        3. Send tool results back to LLM
        4. Repeat until LLM responds without tool calls or max iterations reached

        Args:
            messages: Initial conversation messages
            max_iterations: Maximum tool calling iterations

        Returns:
            Final response dict with 'content' and 'messages' (full conversation)
        """
        conversation = messages.copy()
        tool_definitions = [tool['definition'] for tool in self.tools.values()]
        called_tools: set = set()  # track (tool_name, args_json) to detect loops
        last_content: str = ''

        for iteration in range(max_iterations):
            response = await self.chat_completion(
                messages=conversation,
                tools=tool_definitions if tool_definitions else None
            )

            content = response.get('content') or ''
            if content:
                last_content = content

            # Add assistant response to conversation
            assistant_message = {
                'role': 'assistant',
                'content': content
            }

            if 'tool_calls' in response:
                assistant_message['tool_calls'] = response['tool_calls']

            conversation.append(assistant_message)

            # No tool calls → clean final response
            if 'tool_calls' not in response:
                return {
                    'content': content,
                    'messages': conversation,
                    'iterations': iteration + 1
                }

            # Execute tool calls, detect loops
            loop_detected = False
            for tool_call in response['tool_calls']:
                tool_name = tool_call['function']['name']
                args_raw = tool_call['function']['arguments']
                call_key = (tool_name, args_raw)

                if call_key in called_tools:
                    logger.warning("Tool loop detected: %s called with same args twice, breaking", tool_name)
                    loop_detected = True
                    break

                called_tools.add(call_key)
                arguments = json.loads(args_raw)
                tool_result = await self._execute_tool(tool_name, arguments)

                conversation.append({
                    'role': 'tool',
                    'tool_call_id': tool_call['id'],
                    'name': tool_name,
                    'content': json.dumps(tool_result)
                })

            if loop_detected:
                break

        # Loop exited — ask the model for a plain final answer without tools
        if last_content:
            return {
                'content': last_content,
                'messages': conversation,
                'iterations': max_iterations
            }

        # Last resort: one more call without tools to get a plain response
        try:
            final = await self.chat_completion(messages=conversation, tools=None)
            return {
                'content': final.get('content') or 'I was unable to complete that request. Please try again.',
                'messages': conversation,
                'iterations': max_iterations
            }
        except Exception:
            return {
                'content': 'I was unable to complete that request. Please try again.',
                'messages': conversation,
                'iterations': max_iterations
            }


    async def generate_trend_analysis(
        self,
        metrics: List[Dict[str, Any]],
        athlete_goals: Optional[str] = None,
        current_plan: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate AI-powered weight trend analysis using LangChain structured output.
        
        Requirements: 7.1, 7.2, 7.3
        
        Args:
            metrics: List of body metric records containing:
                - measurement_date: Date of measurement
                - weight: Weight in kg
                - body_fat_pct: Body fat percentage (optional)
            athlete_goals: Athlete's stated goals (optional)
            current_plan: Current training/nutrition plan (optional)
        
        Returns:
            Dict containing structured trend analysis with:
                - weekly_change_rate: Average kg/week change
                - trend_direction: 'increasing', 'decreasing', or 'stable'
                - summary: Brief trend summary
                - goal_alignment: Assessment vs goals
                - recommendations: Actionable suggestions
                - confidence_level: 'high', 'medium', or 'low'
                - data_points_analyzed: Number of measurements
        
        Raises:
            ValueError: If fewer than 4 weeks of data provided
        """
        from app.schemas.trend_analysis import TrendAnalysisResponse
        from datetime import datetime, timedelta
        
        # Validate minimum data requirement (Requirement 7.1)
        if len(metrics) < 4:
            raise ValueError("At least 4 weeks of weight data required for trend analysis")
        
        # Sort metrics by date
        sorted_metrics = sorted(metrics, key=lambda m: m['measurement_date'])
        
        # Calculate weekly average weight change rate (Requirement 7.2)
        first_date = datetime.fromisoformat(str(sorted_metrics[0]['measurement_date']))
        last_date = datetime.fromisoformat(str(sorted_metrics[-1]['measurement_date']))
        first_weight = sorted_metrics[0]['weight']
        last_weight = sorted_metrics[-1]['weight']
        
        days_elapsed = (last_date - first_date).days
        weeks_elapsed = days_elapsed / 7.0
        
        if weeks_elapsed < 4:
            raise ValueError("Data must span at least 4 weeks for trend analysis")
        
        total_change = last_weight - first_weight
        weekly_change_rate = total_change / weeks_elapsed if weeks_elapsed > 0 else 0
        
        # Initialize LangChain ChatOpenAI with structured output
        llm = ChatOpenAI(
            base_url=self.endpoint_url.replace('/v1/chat/completions', ''),
            model=self.model_name,
            temperature=0.1,  # Low temperature for consistent analysis (Requirement 7.3)
            api_key="not-needed"  # Required by LangChain but not used by Ollama/LM Studio
        )
        
        # Use with_structured_output for validated Pydantic schema responses
        structured_llm = llm.with_structured_output(TrendAnalysisResponse)
        
        # Build context from metrics data
        context_parts = []
        
        context_parts.append(f"Weight Measurements ({len(sorted_metrics)} data points over {weeks_elapsed:.1f} weeks):")
        for metric in sorted_metrics:
            date = metric['measurement_date']
            weight = metric['weight']
            bf_pct = metric.get('body_fat_pct')
            if bf_pct:
                context_parts.append(f"  - {date}: {weight:.1f} kg (Body Fat: {bf_pct:.1f}%)")
            else:
                context_parts.append(f"  - {date}: {weight:.1f} kg")
        
        context_parts.append(f"\nCalculated Metrics:")
        context_parts.append(f"  - Total weight change: {total_change:+.2f} kg")
        context_parts.append(f"  - Average weekly change rate: {weekly_change_rate:+.3f} kg/week")
        context_parts.append(f"  - Time period: {weeks_elapsed:.1f} weeks")
        
        # Include athlete goals and plan in context (Requirement 7.2)
        if athlete_goals:
            context_parts.append(f"\nAthlete Goals: {athlete_goals}")
        
        if current_plan:
            context_parts.append(f"\nCurrent Plan: {current_plan}")
        
        context = "\n".join(context_parts)
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert nutrition and body composition coach analyzing weight trends.
Provide a comprehensive trend analysis based on the weight measurement data.

Focus on:
- Overall trend direction and consistency
- Rate of change and whether it's appropriate
- Alignment with athlete's stated goals (if provided)
- Data quality and confidence in the analysis
- Specific, actionable recommendations for adjusting rate of change if needed

Be specific and reference the actual data points and calculated metrics provided.
Consider that healthy weight loss is typically 0.5-1.0 kg/week, and healthy weight gain is 0.25-0.5 kg/week.
Weight maintenance should show minimal weekly change (within ±0.2 kg/week)."""),
            ("user", "Analyze this weight trend:\n\n{context}")
        ])
        
        # Generate structured analysis
        chain = prompt | structured_llm
        
        try:
            result = await chain.ainvoke({"context": context})
            
            # Return as dict for API response
            return {
                'weekly_change_rate': result.weekly_change_rate,
                'trend_direction': result.trend_direction,
                'summary': result.summary,
                'goal_alignment': result.goal_alignment,
                'recommendations': result.recommendations,
                'confidence_level': result.confidence_level,
                'data_points_analyzed': result.data_points_analyzed
            }
            
        except Exception as e:
            # If LLM fails, return a basic analysis based on calculated metrics
            trend_direction = 'stable'
            if abs(weekly_change_rate) < 0.2:
                trend_direction = 'stable'
            elif weekly_change_rate > 0:
                trend_direction = 'increasing'
            else:
                trend_direction = 'decreasing'
            
            return {
                'weekly_change_rate': round(weekly_change_rate, 3),
                'trend_direction': trend_direction,
                'summary': f"Weight has changed by {total_change:+.2f} kg over {weeks_elapsed:.1f} weeks, averaging {weekly_change_rate:+.3f} kg/week.",
                'goal_alignment': "Unable to assess goal alignment - LLM analysis unavailable.",
                'recommendations': "Continue monitoring your weight weekly. Consult with a coach for personalized recommendations.",
                'confidence_level': 'low',
                'data_points_analyzed': len(sorted_metrics)
            }

    async def generate_effort_analysis(self, activity: Dict[str, Any]) -> str:
        """
        Generate AI-powered effort analysis for an activity using LangChain structured output.
        
        Args:
            activity: Activity data dict containing:
                - activity_type: Type of activity (Run, Ride, etc.)
                - distance_m: Distance in meters
                - moving_time_s: Duration in seconds
                - elevation_m: Elevation gain in meters
                - avg_hr: Average heart rate (optional)
                - max_hr: Maximum heart rate (optional)
                - raw_json: Raw activity data with splits and pace info (optional)
        
        Returns:
            Formatted analysis text as a string
        """
        from app.schemas.activity_analysis import EffortAnalysisResponse
        
        # Initialize LangChain ChatOpenAI with structured output
        llm = ChatOpenAI(
            base_url=self.endpoint_url.replace('/v1/chat/completions', ''),
            model=self.model_name,
            temperature=0.1,  # Low temperature for consistent analysis
            api_key="not-needed"  # Required by LangChain but not used by Ollama/LM Studio
        )
        
        # Use with_structured_output for validated Pydantic schema responses
        structured_llm = llm.with_structured_output(EffortAnalysisResponse)
        
        # Build context from activity data
        context_parts = []
        
        # Basic activity info
        activity_type = activity.get('activity_type', 'Unknown')
        distance_km = activity.get('distance_m', 0) / 1000 if activity.get('distance_m') else 0
        duration_min = activity.get('moving_time_s', 0) / 60 if activity.get('moving_time_s') else 0
        elevation_m = activity.get('elevation_m', 0) if activity.get('elevation_m') else 0
        
        context_parts.append(f"Activity Type: {activity_type}")
        context_parts.append(f"Distance: {distance_km:.2f} km")
        context_parts.append(f"Duration: {duration_min:.1f} minutes")
        context_parts.append(f"Elevation Gain: {elevation_m:.0f} meters")
        
        # Calculate pace/speed
        if distance_km > 0 and duration_min > 0:
            if activity_type in ['Run', 'Walk']:
                pace_min_per_km = duration_min / distance_km
                pace_min = int(pace_min_per_km)
                pace_sec = int((pace_min_per_km - pace_min) * 60)
                context_parts.append(f"Average Pace: {pace_min}:{pace_sec:02d} /km")
            else:
                speed_kmh = distance_km / (duration_min / 60)
                context_parts.append(f"Average Speed: {speed_kmh:.1f} km/h")
        
        # Heart rate data
        avg_hr = activity.get('avg_hr')
        max_hr = activity.get('max_hr')
        if avg_hr or max_hr:
            hr_info = []
            if avg_hr:
                hr_info.append(f"Average HR: {avg_hr} bpm")
            if max_hr:
                hr_info.append(f"Max HR: {max_hr} bpm")
            context_parts.append(", ".join(hr_info))
        
        # Parse raw_json for additional context (splits, pace variation)
        raw_json = activity.get('raw_json')
        if raw_json:
            try:
                if isinstance(raw_json, str):
                    raw_data = json.loads(raw_json)
                else:
                    raw_data = raw_json
                
                # Add splits info if available
                splits = raw_data.get('splits_metric') or raw_data.get('splits_standard')
                if splits and len(splits) > 1:
                    # Calculate pace variation
                    paces = []
                    for split in splits:
                        if split.get('moving_time') and split.get('distance') and split['distance'] > 0:
                            pace = (split['moving_time'] / 60) / (split['distance'] / 1000)
                            paces.append(pace)
                    
                    if paces:
                        avg_pace = sum(paces) / len(paces)
                        pace_variation = max(paces) - min(paces)
                        context_parts.append(f"Pace Variation: {pace_variation:.2f} min/km range across {len(splits)} splits")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # If parsing fails, continue without splits data
                pass
        
        context = "\n".join(context_parts)
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert running and cycling coach analyzing activity effort.
Provide a comprehensive effort analysis based on the activity data.

Focus on:
- Overall effort level and intensity
- Heart rate zones and cardiovascular stress (if HR data available)
- Pace consistency and variation patterns
- Impact of elevation on effort
- Actionable recommendations for future training

Be specific and reference the actual data points provided."""),
            ("user", "Analyze this activity:\n\n{context}")
        ])
        
        # Generate structured analysis
        chain = prompt | structured_llm
        
        try:
            result = await chain.ainvoke({"context": context})
            
            # Format the structured response into readable text
            analysis_parts = []
            
            analysis_parts.append(f"**Effort Level:** {result.effort_level}\n")
            analysis_parts.append(f"**Summary:** {result.summary}\n")
            
            if result.heart_rate_analysis:
                analysis_parts.append(f"**Heart Rate Analysis:** {result.heart_rate_analysis}\n")
            
            if result.pace_analysis:
                analysis_parts.append(f"**Pace Analysis:** {result.pace_analysis}\n")
            
            if result.elevation_analysis:
                analysis_parts.append(f"**Elevation Analysis:** {result.elevation_analysis}\n")
            
            analysis_parts.append(f"**Recommendations:** {result.recommendations}")
            
            return "\n".join(analysis_parts)
            
        except Exception as e:
            # If LLM fails, return a basic analysis
            return f"Unable to generate detailed analysis. Activity: {distance_km:.2f}km in {duration_min:.1f} minutes with {elevation_m:.0f}m elevation gain."
        async def generate_trend_analysis(
            self,
            metrics: List[Dict[str, Any]],
            athlete_goals: Optional[str] = None,
            current_plan: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Generate AI-powered weight trend analysis using LangChain structured output.

            Requirements: 7.1, 7.2, 7.3

            Args:
                metrics: List of body metric records containing:
                    - measurement_date: Date of measurement
                    - weight: Weight in kg
                    - body_fat_pct: Body fat percentage (optional)
                athlete_goals: Athlete's stated goals (optional)
                current_plan: Current training/nutrition plan (optional)

            Returns:
                Dict containing structured trend analysis with:
                    - weekly_change_rate: Average kg/week change
                    - trend_direction: 'increasing', 'decreasing', or 'stable'
                    - summary: Brief trend summary
                    - goal_alignment: Assessment vs goals
                    - recommendations: Actionable suggestions
                    - confidence_level: 'high', 'medium', or 'low'
                    - data_points_analyzed: Number of measurements

            Raises:
                ValueError: If fewer than 4 weeks of data provided
            """
            from app.schemas.trend_analysis import TrendAnalysisResponse
            from datetime import datetime, timedelta

            # Validate minimum data requirement (Requirement 7.1)
            if len(metrics) < 4:
                raise ValueError("At least 4 weeks of weight data required for trend analysis")

            # Sort metrics by date
            sorted_metrics = sorted(metrics, key=lambda m: m['measurement_date'])

            # Calculate weekly average weight change rate (Requirement 7.2)
            first_date = datetime.fromisoformat(str(sorted_metrics[0]['measurement_date']))
            last_date = datetime.fromisoformat(str(sorted_metrics[-1]['measurement_date']))
            first_weight = sorted_metrics[0]['weight']
            last_weight = sorted_metrics[-1]['weight']

            days_elapsed = (last_date - first_date).days
            weeks_elapsed = days_elapsed / 7.0

            if weeks_elapsed < 4:
                raise ValueError("Data must span at least 4 weeks for trend analysis")

            total_change = last_weight - first_weight
            weekly_change_rate = total_change / weeks_elapsed if weeks_elapsed > 0 else 0

            # Initialize LangChain ChatOpenAI with structured output
            llm = ChatOpenAI(
                base_url=self.endpoint_url.replace('/v1/chat/completions', ''),
                model=self.model_name,
                temperature=0.1,  # Low temperature for consistent analysis (Requirement 7.3)
                api_key="not-needed"  # Required by LangChain but not used by Ollama/LM Studio
            )

            # Use with_structured_output for validated Pydantic schema responses
            structured_llm = llm.with_structured_output(TrendAnalysisResponse)

            # Build context from metrics data
            context_parts = []

            context_parts.append(f"Weight Measurements ({len(sorted_metrics)} data points over {weeks_elapsed:.1f} weeks):")
            for metric in sorted_metrics:
                date = metric['measurement_date']
                weight = metric['weight']
                bf_pct = metric.get('body_fat_pct')
                if bf_pct:
                    context_parts.append(f"  - {date}: {weight:.1f} kg (Body Fat: {bf_pct:.1f}%)")
                else:
                    context_parts.append(f"  - {date}: {weight:.1f} kg")

            context_parts.append(f"\nCalculated Metrics:")
            context_parts.append(f"  - Total weight change: {total_change:+.2f} kg")
            context_parts.append(f"  - Average weekly change rate: {weekly_change_rate:+.3f} kg/week")
            context_parts.append(f"  - Time period: {weeks_elapsed:.1f} weeks")

            # Include athlete goals and plan in context (Requirement 7.2)
            if athlete_goals:
                context_parts.append(f"\nAthlete Goals: {athlete_goals}")

            if current_plan:
                context_parts.append(f"\nCurrent Plan: {current_plan}")

            context = "\n".join(context_parts)

            # Create prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert nutrition and body composition coach analyzing weight trends.
    Provide a comprehensive trend analysis based on the weight measurement data.

    Focus on:
    - Overall trend direction and consistency
    - Rate of change and whether it's appropriate
    - Alignment with athlete's stated goals (if provided)
    - Data quality and confidence in the analysis
    - Specific, actionable recommendations for adjusting rate of change if needed

    Be specific and reference the actual data points and calculated metrics provided.
    Consider that healthy weight loss is typically 0.5-1.0 kg/week, and healthy weight gain is 0.25-0.5 kg/week.
    Weight maintenance should show minimal weekly change (within ±0.2 kg/week)."""),
                ("user", "Analyze this weight trend:\n\n{context}")
            ])

            # Generate structured analysis
            chain = prompt | structured_llm

            try:
                result = await chain.ainvoke({"context": context})

                # Return as dict for API response
                return {
                    'weekly_change_rate': result.weekly_change_rate,
                    'trend_direction': result.trend_direction,
                    'summary': result.summary,
                    'goal_alignment': result.goal_alignment,
                    'recommendations': result.recommendations,
                    'confidence_level': result.confidence_level,
                    'data_points_analyzed': result.data_points_analyzed
                }

            except Exception as e:
                # If LLM fails, return a basic analysis based on calculated metrics
                trend_direction = 'stable'
                if abs(weekly_change_rate) < 0.2:
                    trend_direction = 'stable'
                elif weekly_change_rate > 0:
                    trend_direction = 'increasing'
                else:
                    trend_direction = 'decreasing'

                return {
                    'weekly_change_rate': round(weekly_change_rate, 3),
                    'trend_direction': trend_direction,
                    'summary': f"Weight has changed by {total_change:+.2f} kg over {weeks_elapsed:.1f} weeks, averaging {weekly_change_rate:+.3f} kg/week.",
                    'goal_alignment': "Unable to assess goal alignment - LLM analysis unavailable.",
                    'recommendations': "Continue monitoring your weight weekly. Consult with a coach for personalized recommendations.",
                    'confidence_level': 'low',
                    'data_points_analyzed': len(sorted_metrics)
                }



# Legacy function for backward compatibility
async def generate_evaluation(contract: dict) -> str:
    """
    Send the contract to LM Studio or Ollama and return the raw JSON string response.
    Retries up to 3 times with exponential backoff on connection errors.
    Raises ValueError if the response is not valid JSON.
    """
    settings = get_settings()
    
    # Use a simple default system prompt since this is legacy code
    # DEPRECATED: This function is maintained for backward compatibility with tests only.
    # New code should use EvaluationEngine or LangChainEvaluationService with Context Engineering.
    system_prompt = """You are an expert fitness coach analyzing weekly performance data.
Analyze the provided data and generate a comprehensive evaluation in JSON format."""
    
    user_message = json.dumps(contract, indent=2, default=str)

    # Choose model based on backend
    model_name = settings.OLLAMA_MODEL if settings.is_ollama else settings.LM_STUDIO_MODEL

    payload = {
        "model": model_name,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    }
    
    # Construct endpoint URL using normalization to handle /api suffix and trailing slashes
    endpoint_url = construct_openai_endpoint(settings.llm_base_url)

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload
                )
                response.raise_for_status()
                raw = response.json()["choices"][0]["message"]["content"]
                json.loads(raw)  # validate it's parseable
                return raw
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
