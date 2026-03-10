"""Chat Tools for LLM

Provides tool execution framework and tool implementations for the chat system.
All tools enforce user_id scoping for security.

Requirements: 6.1-6.7, 20.3
"""
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import httpx

from app.services.goal_service import GoalService
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.config import get_settings

logger = logging.getLogger(__name__)


class ChatToolsError(Exception):
    """Base exception for chat tools errors."""
    pass


class UserIdMissingError(ChatToolsError):
    """Raised when user_id is required but not provided."""
    pass


class ToolExecutionError(ChatToolsError):
    """Raised when tool execution fails."""
    pass


async def execute_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    user_id: Optional[int],
    db: Session
) -> Dict[str, Any]:
    """
    Execute a chat tool with user_id scoping and error handling.
    
    This is the main entry point for all tool executions. It validates
    user_id presence, routes to the appropriate tool implementation,
    and handles errors gracefully.
    
    Args:
        tool_name: Name of the tool to execute
        parameters: Tool parameters from LLM
        user_id: Requesting user ID (required for security)
        db: Database session
    
    Returns:
        Tool execution result as dict
    
    Raises:
        UserIdMissingError: If user_id is None
        ToolExecutionError: If tool execution fails
    
    Requirements: 6.7, 20.3
    """
    # Validate user_id presence
    if user_id is None:
        logger.error(f"Tool {tool_name} called without user_id")
        raise UserIdMissingError(f"user_id is required for tool {tool_name}")
    
    logger.info(f"Executing tool {tool_name} for user_id={user_id} with parameters={parameters}")
    
    try:
        # Route to appropriate tool implementation
        if tool_name == "save_athlete_goal":
            return await _save_athlete_goal(parameters, user_id, db)
        elif tool_name == "get_my_goals":
            return await _get_my_goals(parameters, user_id, db)
        elif tool_name == "get_my_recent_activities":
            return await _get_my_recent_activities(parameters, user_id, db)
        elif tool_name == "get_my_weekly_metrics":
            return await _get_my_weekly_metrics(parameters, user_id, db)
        elif tool_name == "save_training_plan":
            return await _save_training_plan(parameters, user_id, db)
        elif tool_name == "get_training_plan":
            return await _get_training_plan(parameters, user_id, db)
        elif tool_name == "search_web":
            return await _search_web(parameters, user_id, db)
        else:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")
    
    except UserIdMissingError:
        raise
    except Exception as e:
        logger.error(f"Tool {tool_name} execution failed: {str(e)}", exc_info=True)
        raise ToolExecutionError(f"Tool {tool_name} failed: {str(e)}") from e


# Tool Implementations

async def _save_athlete_goal(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Save an athlete goal.
    
    Requirements: 6.1
    """
    goal_service = GoalService(db)
    
    # Add athlete_id to parameters (using user_id)
    parameters['athlete_id'] = str(user_id)
    
    result = goal_service.save_goal(
        goal_type=parameters.get('goal_type'),
        description=parameters.get('description'),
        target_value=parameters.get('target_value'),
        target_date=parameters.get('target_date'),
        athlete_id=parameters.get('athlete_id')
    )
    
    logger.info(f"Goal saved for user_id={user_id}: {result['goal_id']}")
    return result


async def _get_my_goals(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Retrieve athlete's goals.
    
    Requirements: 6.2
    """
    goal_service = GoalService(db)
    
    goals = goal_service.get_active_goals(athlete_id=str(user_id))
    
    result = {
        'success': True,
        'goals': [goal.to_dict() for goal in goals],
        'count': len(goals)
    }
    
    logger.info(f"Retrieved {len(goals)} goals for user_id={user_id}")
    return result


async def _get_my_recent_activities(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Retrieve recent Strava activities.
    
    Requirements: 6.3
    """
    days = parameters.get('days', 28)
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # Query activities with user_id scoping
    activities = db.query(StravaActivity)\
        .filter(StravaActivity.athlete_id == user_id)\
        .filter(StravaActivity.start_date >= cutoff_date)\
        .order_by(StravaActivity.start_date.desc())\
        .all()
    
    # Format activities
    formatted_activities = []
    for activity in activities:
        formatted_activities.append({
            'id': activity.id,
            'strava_id': activity.strava_id,
            'activity_type': activity.activity_type,
            'start_date': activity.start_date.isoformat(),
            'moving_time_s': activity.moving_time_s,
            'distance_m': activity.distance_m,
            'elevation_m': activity.elevation_m,
            'avg_hr': activity.avg_hr,
            'max_hr': activity.max_hr,
            'calories': activity.calories
        })
    
    result = {
        'success': True,
        'activities': formatted_activities,
        'count': len(formatted_activities),
        'days': days
    }
    
    logger.info(f"Retrieved {len(formatted_activities)} activities for user_id={user_id} (last {days} days)")
    return result


async def _get_my_weekly_metrics(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Retrieve aggregated weekly training metrics.
    
    Requirements: 6.4
    """
    weeks = parameters.get('weeks', 4)
    
    # Calculate week range
    today = date.today()
    week_starts = []
    for i in range(weeks):
        # Calculate Monday of each week going backwards
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday + (i * 7))
        week_starts.append(week_start)
    
    # Query weekly measurements
    weekly_data = []
    for week_start in week_starts:
        measurement = db.query(WeeklyMeasurement)\
            .filter(WeeklyMeasurement.week_start == week_start)\
            .first()
        
        if measurement:
            # Get activities for this week
            week_end = week_start + timedelta(days=7)
            activities = db.query(StravaActivity)\
                .filter(StravaActivity.athlete_id == user_id)\
                .filter(StravaActivity.start_date >= datetime.combine(week_start, datetime.min.time()))\
                .filter(StravaActivity.start_date < datetime.combine(week_end, datetime.min.time()))\
                .all()
            
            # Calculate aggregates
            total_distance_km = sum((a.distance_m or 0) / 1000 for a in activities)
            total_time_hours = sum((a.moving_time_s or 0) / 3600 for a in activities)
            total_elevation_m = sum((a.elevation_m or 0) for a in activities)
            activity_count = len(activities)
            
            weekly_data.append({
                'week_start': week_start.isoformat(),
                'week_id': measurement.week_id,
                'activity_count': activity_count,
                'total_distance_km': round(total_distance_km, 2),
                'total_time_hours': round(total_time_hours, 2),
                'total_elevation_m': round(total_elevation_m, 1),
                'avg_resting_hr': measurement.avg_resting_hr,
                'avg_weight_kg': measurement.avg_weight_kg
            })
    
    result = {
        'success': True,
        'weekly_metrics': weekly_data,
        'weeks': weeks
    }
    
    logger.info(f"Retrieved {len(weekly_data)} weeks of metrics for user_id={user_id}")
    return result


async def _save_training_plan(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Save a training plan.
    
    Requirements: 6.5
    """
    # Lazy import to avoid circular dependency
    from app.services.training_plan_engine import TrainingPlanEngine
    from app.services.llm_client import LLMClient
    
    # Initialize training plan engine
    llm_client = LLMClient()
    plan_engine = TrainingPlanEngine(db, llm_client)
    
    # Parse plan from parameters
    # The LLM should provide the plan in the expected format
    plan_text = parameters.get('plan_text')
    if not plan_text:
        raise ValueError("plan_text parameter is required")
    
    # Parse the plan
    plan = plan_engine.parse_plan(plan_text)
    
    # Set user_id
    plan.user_id = user_id
    
    # Save the plan
    plan_id = plan_engine.save_plan(plan)
    
    result = {
        'success': True,
        'plan_id': plan_id,
        'message': f"Training plan '{plan.title}' saved successfully"
    }
    
    logger.info(f"Training plan saved for user_id={user_id}: {plan_id}")
    return result


async def _get_training_plan(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Retrieve a training plan.
    
    Requirements: 6.6
    """
    # Lazy import to avoid circular dependency
    from app.services.training_plan_engine import TrainingPlanEngine
    from app.services.llm_client import LLMClient
    
    plan_id = parameters.get('plan_id')
    if not plan_id:
        raise ValueError("plan_id parameter is required")
    
    # Initialize training plan engine
    llm_client = LLMClient()
    plan_engine = TrainingPlanEngine(db, llm_client)
    
    # Get plan with user_id scoping
    plan = plan_engine.get_plan(plan_id, user_id)
    
    if not plan:
        return {
            'success': False,
            'message': f"Training plan {plan_id} not found"
        }
    
    # Format plan as human-readable text
    plan_text = plan_engine.pretty_print(plan)
    
    result = {
        'success': True,
        'plan_id': plan.id,
        'plan_text': plan_text,
        'plan': {
            'title': plan.title,
            'sport': plan.sport,
            'start_date': plan.start_date.isoformat(),
            'end_date': plan.end_date.isoformat(),
            'status': plan.status,
            'weeks_count': len(plan.weeks)
        }
    }
    
    logger.info(f"Retrieved training plan {plan_id} for user_id={user_id}")
    return result


async def _search_web(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Search the web using Tavily API.
    
    Requirements: 5.1, 5.2, 5.3
    """
    settings = get_settings()
    
    if not settings.TAVILY_API_KEY:
        raise ToolExecutionError("Tavily API key not configured")
    
    query = parameters.get('query')
    if not query:
        raise ValueError("query parameter is required")
    
    # Call Tavily API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 5
            },
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
    
    # Format results with citations
    results = []
    for item in data.get('results', []):
        results.append({
            'title': item.get('title'),
            'url': item.get('url'),
            'content': item.get('content'),
            'score': item.get('score')
        })
    
    result = {
        'success': True,
        'query': query,
        'answer': data.get('answer'),
        'results': results,
        'sources': [r['url'] for r in results]
    }
    
    logger.info(f"Web search completed for user_id={user_id}: {query}")
    return result


# Tool Definitions for LLM

def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get all tool definitions for LLM function calling.
    
    Returns:
        List of tool definition dicts compatible with Ollama/OpenAI function calling
    """
    return [
        {
            'type': 'function',
            'function': {
                'name': 'save_athlete_goal',
                'description': (
                    'Save a new fitness goal for the athlete. Use this tool after gathering '
                    'sufficient information about the athlete\'s goal through conversation. '
                    'Ask clarifying questions about timeframe, specific targets, and any constraints '
                    'before calling this tool.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'goal_type': {
                            'type': 'string',
                            'enum': ['weight_loss', 'weight_gain', 'performance', 'endurance', 'strength', 'custom'],
                            'description': 'The type of fitness goal'
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Detailed description of the goal including context from the conversation'
                        },
                        'target_value': {
                            'type': 'number',
                            'description': 'Optional numeric target (e.g., target weight in kg for weight goals)'
                        },
                        'target_date': {
                            'type': 'string',
                            'description': 'Optional target completion date in YYYY-MM-DD format'
                        }
                    },
                    'required': ['goal_type', 'description']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_my_goals',
                'description': 'Retrieve the athlete\'s saved fitness goals',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_my_recent_activities',
                'description': 'Retrieve recent Strava activities for the athlete',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'days': {
                            'type': 'integer',
                            'description': 'Number of days to look back (default: 28)',
                            'default': 28
                        }
                    },
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_my_weekly_metrics',
                'description': 'Retrieve aggregated weekly training metrics for the athlete',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'weeks': {
                            'type': 'integer',
                            'description': 'Number of weeks to retrieve (default: 4)',
                            'default': 4
                        }
                    },
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'save_training_plan',
                'description': (
                    'Save a generated training plan for the athlete. The plan should be '
                    'formatted as markdown text following the standard training plan format.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'plan_text': {
                            'type': 'string',
                            'description': 'The training plan in markdown format'
                        }
                    },
                    'required': ['plan_text']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_training_plan',
                'description': 'Retrieve an existing training plan by ID',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'plan_id': {
                            'type': 'string',
                            'description': 'The training plan ID'
                        }
                    },
                    'required': ['plan_id']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'search_web',
                'description': (
                    'Search the web for current fitness information, training advice, '
                    'or domain knowledge. Use this when you need up-to-date information '
                    'that may not be in your training data.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'The search query'
                        }
                    },
                    'required': ['query']
                }
            }
        }
    ]
