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
        elif tool_name in ("get_my_recent_activities", "query_activities"):
            return await _query_activities(parameters, user_id, db)
        elif tool_name == "get_my_weekly_metrics":
            return await _get_my_weekly_metrics(parameters, user_id, db)
        elif tool_name == "save_training_plan":
            return await _save_training_plan(parameters, user_id, db)
        elif tool_name == "get_training_plan":
            return await _get_training_plan(parameters, user_id, db)
        elif tool_name == "search_web":
            return await _search_web(parameters, user_id, db)
        elif tool_name == "analyze_recent_workout":
            return await _analyze_recent_workout(parameters, user_id, db)
        elif tool_name == "fetch_strava_activity_detail":
            return await _fetch_strava_activity_detail(parameters, user_id, db)
        elif tool_name == "evaluate_recovery":
            return await _evaluate_recovery(parameters, user_id, db)
        elif tool_name == "evaluate_progress":
            return await _evaluate_progress(parameters, user_id, db)
        elif tool_name == "generate_plan":
            return await _generate_plan(parameters, user_id, db)
        elif tool_name == "evaluate_performance_goal":
            return await _evaluate_performance_goal(parameters, user_id, db)
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


# ── query_activities engine ───────────────────────────────────────────────────

from sqlalchemy import func as _func

_QA_FIELDS = {
    "sport_type":    StravaActivity.sport_type,
    "activity_type": StravaActivity.activity_type,
    "distance_m":    StravaActivity.distance_m,
    "moving_time_s": StravaActivity.moving_time_s,
    "elevation_m":   StravaActivity.elevation_m,
    "start_date":    StravaActivity.start_date,
    "avg_hr":        StravaActivity.avg_hr,
    "max_hr":        StravaActivity.max_hr,
    "calories":      StravaActivity.calories,
    "avg_watts":     StravaActivity.avg_watts,
    "avg_cadence":   StravaActivity.avg_cadence,
    "suffer_score":  StravaActivity.suffer_score,
    "trainer":       StravaActivity.trainer,
}

_QA_AGG_FUNCS = {
    "count":  _func.count,
    "sum":    _func.sum,
    "avg":    _func.avg,
    "max":    _func.max,
    "min":    _func.min,
}


def _qa_apply_filter(query, col, op: str, value):
    """Apply a single filter condition to a SQLAlchemy query."""
    if op == "eq":     return query.filter(col == value)
    if op == "ne":     return query.filter(col != value)
    if op == "gt":     return query.filter(col > value)
    if op == "gte":    return query.filter(col >= value)
    if op == "lt":     return query.filter(col < value)
    if op == "lte":    return query.filter(col <= value)
    if op == "in":     return query.filter(col.in_(value))
    if op == "not_in": return query.filter(col.notin_(value))
    raise ValueError(f"Unknown operator: {op}")


_QA_NUMERIC_FIELDS = {
    "distance_m", "moving_time_s", "elevation_m",
    "avg_hr", "max_hr", "calories", "avg_watts", "avg_cadence", "suffer_score",
}


def _qa_parse_value(field: str, value):
    """Coerce filter values to the correct Python type."""
    if field == "start_date" and isinstance(value, str):
        from dateutil.parser import parse as _dp
        return _dp(value)
    # LLMs sometimes emit numeric values as strings — cast them
    if field in _QA_NUMERIC_FIELDS and isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            pass
    return value


async def _query_activities(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Flexible activity query engine.

    Supports arbitrary filters, sort, limit, and aggregate metrics.
    Always scoped to the requesting athlete.
    """
    filters   = parameters.get("filters", [])
    sort      = parameters.get("sort", [{"field": "start_date", "dir": "desc"}])
    limit     = min(int(parameters.get("limit", 20)), 100)
    aggregate = parameters.get("aggregate")  # optional dict with "metrics" list

    # ── Base query (always athlete-scoped) ──────────────────────────────────
    query = db.query(StravaActivity).filter(StravaActivity.athlete_id == user_id)

    # ── Filters ─────────────────────────────────────────────────────────────
    for f in filters:
        # Accept "key"/"name" as aliases for "field"
        field = f.get("field") or f.get("key") or f.get("name", "")
        op    = f.get("op") or f.get("operator", "eq")
        value = f.get("value")
        col   = _QA_FIELDS.get(field)
        if col is None:
            return {"success": False, "error": f"Unknown filter field: {field!r}. "
                    f"Available: {list(_QA_FIELDS)}"}
        value = _qa_parse_value(field, value)
        try:
            query = _qa_apply_filter(query, col, op, value)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    # ── Aggregation path ────────────────────────────────────────────────────
    if aggregate:
        metrics_raw = aggregate.get("metrics", ["count"])
        select_exprs = []
        labels = []
        for metric in metrics_raw:
            if ":" in metric:
                agg_name, field_name = metric.split(":", 1)
            else:
                agg_name, field_name = metric, "start_date"  # count(*) uses any col
            agg_fn = _QA_AGG_FUNCS.get(agg_name)
            col    = _QA_FIELDS.get(field_name)
            if agg_fn is None or col is None:
                return {"success": False, "error": f"Invalid aggregate: {metric!r}"}
            label = metric.replace(":", "_")
            select_exprs.append(agg_fn(col).label(label))
            labels.append(label)

        row = db.query(*select_exprs).filter(StravaActivity.athlete_id == user_id)
        for f in filters:
            col = _QA_FIELDS.get(f["field"])
            if col:
                row = _qa_apply_filter(row, col, f["op"],
                                       _qa_parse_value(f["field"], f["value"]))
        row = row.one()
        results = {label: getattr(row, label) for label in labels}
        # Round floats for readability
        for k, v in results.items():
            if isinstance(v, float):
                results[k] = round(v, 2)
        logger.info("query_activities aggregate: %s (user=%d)", results, user_id)
        return {"success": True, "aggregate": results, "filters_applied": len(filters)}

    # ── Sort ────────────────────────────────────────────────────────────────
    for s in sort:
        # Accept "key" as an alias for "field" (some models use alternate naming)
        field = s.get("field") or s.get("key", "start_date")
        direction = (s.get("dir") or s.get("order", "desc")).lower()
        col = _QA_FIELDS.get(field)
        if col is None:
            return {"success": False, "error": f"Unknown sort field: {field!r}"}
        order_expr = col.desc().nullslast() if direction == "desc" else col.asc().nullsfirst()
        query = query.order_by(order_expr)

    # ── Limit & format ──────────────────────────────────────────────────────
    activities = query.limit(limit).all()

    formatted = [
        {
            "strava_id":     a.strava_id,
            "sport_type":    a.sport_type or a.activity_type,
            "start_date":    a.start_date.strftime("%Y-%m-%d") if a.start_date else None,
            "distance_km":   round(a.distance_m / 1000, 2) if a.distance_m else None,
            "moving_time_s": a.moving_time_s,
            "elevation_m":   a.elevation_m,
            "avg_hr":        a.avg_hr,
            "avg_watts":     a.avg_watts,
            "avg_cadence":   a.avg_cadence,
            "suffer_score":  a.suffer_score,
            "calories":      a.calories,
        }
        for a in activities
    ]

    logger.info("query_activities: %d results (user=%d filters=%d)", len(formatted), user_id, len(filters))
    return {
        "success":    True,
        "activities": formatted,
        "count":      len(formatted),
    }


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
                'activity_count': activity_count,
                'total_distance_km': round(total_distance_km, 2),
                'total_time_hours': round(total_time_hours, 2),
                'total_elevation_m': round(total_elevation_m, 1),
                'rhr_bpm': measurement.rhr_bpm,
                'weight_kg': measurement.weight_kg,
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


async def _analyze_recent_workout(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Full pipeline: WorkoutAnalyzer → FitnessStateBuilder → CoachSynthesizer.
    Returns a structured coaching response for the athlete's most recent workout(s).
    """
    from app.ai.skills.workout_analyzer import WorkoutAnalyzer
    from app.ai.skills.fitness_state_builder import FitnessStateBuilder
    from app.ai.skills.coach_synthesizer import CoachSynthesizer
    from app.ai.skills.schemas import (
        WorkoutAnalyzerInput, FitnessStateInput, CoachInput,
    )

    n_recent = int(parameters.get("n_recent", 1))
    strava_id = parameters.get("strava_id")
    user_question = parameters.get("user_question", "")

    # 1. Analyse recent workout(s)
    analyzer = WorkoutAnalyzer(db, user_id)
    analyses = await analyzer.run(
        WorkoutAnalyzerInput(
            strava_id=strava_id,
            n_recent=n_recent,
        )
    )

    latest = analyses[0] if analyses else None

    # 2. Build / refresh athlete fitness state
    state_builder = FitnessStateBuilder(db, user_id)
    fitness_state = await state_builder.run(FitnessStateInput(lookback_days=28))

    # 3. Load per-sport profile for the analysed activity's sport group
    sport_profile_dict: Optional[dict] = None
    if latest:
        _SPORT_GROUP_MAP = {
            "Ride": "ride", "VirtualRide": "ride", "MountainBikeRide": "ride",
            "GravelRide": "ride", "EBikeRide": "ride",
            "Run": "run", "VirtualRun": "run", "TrailRun": "run",
            "Swim": "swim", "OpenWaterSwim": "swim",
        }
        sport = latest.sport_type or latest.activity_type or ""
        sport_group = _SPORT_GROUP_MAP.get(sport)
        if sport_group:
            try:
                from app.models.athlete_sport_profile import AthleteSportProfile
                sp = (
                    db.query(AthleteSportProfile)
                    .filter_by(athlete_id=user_id, sport_group=sport_group)
                    .first()
                )
                if sp:
                    sport_profile_dict = {
                        "sport_group":                sport_group,
                        "typical_cadence_rpm":        sp.typical_cadence_rpm,
                        "indoor_cadence_rpm":         sp.indoor_cadence_rpm,
                        "outdoor_cadence_rpm":        sp.outdoor_cadence_rpm,
                        "ftp_estimate_w":             sp.ftp_estimate_w,
                        "ftp_confidence":             sp.ftp_confidence,
                        "avg_power_baseline_w":       sp.avg_power_baseline_w,
                        "max_hr_estimate":            sp.max_hr_estimate,
                        "typical_endurance_speed_kmh": sp.typical_endurance_speed_kmh,
                        "best_long_speed_kmh":        sp.best_long_speed_kmh,
                        "weekly_volume_km":           sp.weekly_volume_km,
                        "current_limiters":           sp.current_limiters,
                        "current_strengths":          sp.current_strengths,
                        "profile_confidence":         sp.profile_confidence,
                    }
            except Exception as exc:
                logger.warning("Could not load sport profile for workout analysis: %s", exc)

    # 4. Synthesise coaching response with full athlete context
    synthesizer = CoachSynthesizer(db, user_id)
    coach_response = await synthesizer.run(
        CoachInput(
            workout_analysis=latest,
            fitness_state=fitness_state,
            sport_profile=sport_profile_dict,
            user_question=user_question,
        )
    )

    result = {
        "success": True,
        "headline": coach_response.headline,
        "body": coach_response.body,
        "next_action": coach_response.next_action,
        "confidence": coach_response.confidence,
        "evidence_refs": coach_response.evidence_refs,
        "analyses_count": len(analyses),
    }

    if latest:
        result["latest_workout"] = {
            "strava_id": latest.strava_id,
            "sport_type": latest.sport_type or latest.activity_type,
            "start_date": latest.start_date.isoformat(),
            "cadence_quality": latest.cadence_quality,
            "effort_level": latest.effort_level,
            "limiter_hypothesis": latest.limiter_hypothesis,
            "main_insight": latest.main_insight,
            "next_action": latest.next_action,
        }

    if fitness_state:
        result["fitness_state"] = {
            "fatigue_level": fitness_state.fatigue_level,
            "acwr_ratio": fitness_state.acwr_ratio,
            "current_limiter": fitness_state.current_limiter,
            "limiter_confidence": fitness_state.limiter_confidence,
            "state_confidence": fitness_state.state_confidence,
            "fitness_score": fitness_state.fitness_score,
            "athlete_classification": fitness_state.athlete_classification,
        }

    logger.info("analyze_recent_workout completed for user_id=%d", user_id)
    return result


async def _evaluate_recovery(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Evaluate athlete recovery readiness: ACWR, RHR trend, fatigue level,
    and a specific coaching recommendation.
    """
    from app.ai.skills.recovery_analyzer import RecoveryAnalyzer
    from app.ai.skills.coach_synthesizer import CoachSynthesizer
    from app.ai.skills.schemas import RecoveryInput, CoachInput
    from app.models.athlete_fitness_state import AthleteFitnessState

    lookback_days = int(parameters.get("lookback_days", 28))
    user_question = parameters.get("user_question", "")

    recovery = await RecoveryAnalyzer(db, user_id).run(RecoveryInput(lookback_days=lookback_days))

    # Load persisted fitness state if available (may be stale but avoids rerunning the full pipeline)
    fitness_state_row = (
        db.query(AthleteFitnessState)
        .filter(AthleteFitnessState.athlete_id == user_id)
        .first()
    )
    fitness_state = None
    if fitness_state_row:
        from app.ai.skills.schemas import FitnessState
        from datetime import datetime, timezone
        fitness_state = FitnessState(
            athlete_id=fitness_state_row.athlete_id,
            comfort_cadence_indoor=fitness_state_row.comfort_cadence_indoor,
            comfort_cadence_outdoor=fitness_state_row.comfort_cadence_outdoor,
            climbing_cadence=fitness_state_row.climbing_cadence,
            current_limiter=fitness_state_row.current_limiter,
            limiter_confidence=fitness_state_row.limiter_confidence or 0.0,
            fatigue_level=fitness_state_row.fatigue_level or "low",
            weekly_consistency=fitness_state_row.weekly_consistency or 0.0,
            acwr_ratio=fitness_state_row.acwr_ratio,
            hr_response_trend=fitness_state_row.hr_response_trend,
            rhr_trend=fitness_state_row.rhr_trend,
            state_confidence=fitness_state_row.state_confidence or 0.0,
            last_updated_at=fitness_state_row.last_updated_at or datetime.now(timezone.utc),
            summary_text=fitness_state_row.summary_text,
        )

    coach_response = await CoachSynthesizer(db, user_id).run(
        CoachInput(
            recovery_status=recovery,
            fitness_state=fitness_state,
            user_question=user_question,
        )
    )

    logger.info("evaluate_recovery completed for user_id=%d", user_id)
    return {
        "success": True,
        "headline": coach_response.headline,
        "body": coach_response.body,
        "next_action": coach_response.next_action,
        "confidence": coach_response.confidence,
        "evidence_refs": coach_response.evidence_refs,
        "recovery": {
            "fatigue_level": recovery.fatigue_level,
            "acwr_ratio": recovery.acwr_ratio,
            "acute_load_min": recovery.acute_load_min,
            "chronic_load_min": recovery.chronic_load_min,
            "rhr_bpm": recovery.rhr_bpm,
            "rhr_trend": recovery.rhr_trend,
            "rest_recommended": recovery.rest_recommended,
            "recommendation": recovery.recommendation,
        },
    }


async def _generate_plan(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Generate a training plan (and optionally nutrition targets) grounded in
    the athlete's current fitness state, goals, and recovery status.

    Saves the training plan to the DB and optionally upserts PlanTargets.
    """
    from app.ai.skills.training_planner import TrainingPlanner, TrainingPlannerInput
    from app.ai.skills.nutrition_evaluator import NutritionEvaluator
    from app.ai.skills.progress_analyzer import ProgressAnalyzer
    from app.ai.skills.coach_synthesizer import CoachSynthesizer
    from app.ai.skills.schemas import NutritionInput, ProgressInput, CoachInput
    from app.models.athlete_fitness_state import AthleteFitnessState
    from app.models.plan_targets import PlanTargets

    plan_type     = parameters.get("plan_type", "training")   # training | nutrition | both
    duration_weeks = int(parameters.get("duration_weeks", 4))
    goal_id       = parameters.get("goal_id")
    user_question = parameters.get("user_question", "")

    # ── Build context for the planner ────────────────────────────────────────

    context: dict = {"user_question": user_question, "duration_weeks": duration_weeks}

    # Load cached fitness state
    fs_row = db.query(AthleteFitnessState).filter(
        AthleteFitnessState.athlete_id == user_id
    ).first()
    if fs_row:
        context["fitness_state"] = {
            "current_limiter":    fs_row.current_limiter,
            "limiter_confidence": fs_row.limiter_confidence,
            "fatigue_level":      fs_row.fatigue_level,
            "acwr_ratio":         fs_row.acwr_ratio,
            "weekly_consistency": fs_row.weekly_consistency,
            "hr_response_trend":  fs_row.hr_response_trend,
            "comfort_cadence_indoor":  fs_row.comfort_cadence_indoor,
            "comfort_cadence_outdoor": fs_row.comfort_cadence_outdoor,
            "summary":            fs_row.summary_text,
        }

    # Nutrition context
    nutrition_eval = await NutritionEvaluator(db, user_id).run(NutritionInput())
    context["nutrition"] = {
        "days_logged":          nutrition_eval.days_logged,
        "avg_calories":         nutrition_eval.avg_calories,
        "avg_protein_g":        nutrition_eval.avg_protein_g,
        "calorie_adherence_pct": nutrition_eval.calorie_adherence_pct,
        "assessment":           nutrition_eval.assessment,
    }

    # Goal context
    progress_report = await ProgressAnalyzer(db, user_id).run(ProgressInput(goal_id=goal_id))
    context["goals"] = [
        {
            "goal_type":   g.goal_type,
            "description": g.description,
            "trend":       g.trend,
            "gap":         g.gap,
        }
        for g in progress_report.goals
    ]

    result: dict = {"success": True}

    # ── Training plan ─────────────────────────────────────────────────────────

    if plan_type in ("training", "both"):
        planner_output = await TrainingPlanner(db, user_id).run(
            TrainingPlannerInput(
                duration_weeks=duration_weeks,
                goal_id=goal_id,
                context=context,
            )
        )
        result["training_plan"] = {
            "plan_id":  planner_output.plan_id,
            "title":    planner_output.title,
            "sport":    planner_output.sport,
            "weeks":    planner_output.weeks,
            "summary":  planner_output.summary,
        }

    # ── Nutrition targets ─────────────────────────────────────────────────────

    if plan_type in ("nutrition", "both"):
        targets = _compute_nutrition_targets(context, db, user_id)
        if targets:
            _upsert_plan_targets(db, user_id, targets)
            result["nutrition_targets"] = targets

    # ── Coaching framing ──────────────────────────────────────────────────────

    coach_response = await CoachSynthesizer(db, user_id).run(
        CoachInput(
            nutrition_eval=nutrition_eval,
            progress_report=progress_report,
            user_question=user_question,
        )
    )
    result["headline"]      = coach_response.headline
    result["body"]          = coach_response.body
    result["next_action"]   = coach_response.next_action
    result["confidence"]    = coach_response.confidence
    result["evidence_refs"] = coach_response.evidence_refs

    logger.info("generate_plan (%s) completed for user_id=%d", plan_type, user_id)
    return result


def _compute_nutrition_targets(context: dict, db, user_id: int) -> Optional[dict]:
    """
    Compute simple evidence-based nutrition targets from athlete context.
    Uses weight from WeeklyMeasurement + activity load for TDEE estimate.
    """
    from app.models.weekly_measurement import WeeklyMeasurement

    row = (
        db.query(WeeklyMeasurement.weight_kg, WeeklyMeasurement.rhr_bpm)
        .filter(
            WeeklyMeasurement.athlete_id == user_id,
            WeeklyMeasurement.weight_kg.isnot(None),
        )
        .order_by(WeeklyMeasurement.week_start.desc())
        .first()
    )
    if not row:
        return None

    weight_kg = row[0]
    goals = context.get("goals", [])
    goal_types = {g["goal_type"] for g in goals}

    # Simple TDEE: Mifflin–St Jeor (sedentary base) × 1.55 (moderately active)
    # Without height/age we use weight-based approximation
    bmr = 10 * weight_kg + 500   # rough unisex approximation
    tdee = round(bmr * 1.55)

    # Calorie target
    if "weight_loss" in goal_types:
        cal_target = tdee - 400
    elif "weight_gain" in goal_types:
        cal_target = tdee + 300
    else:
        cal_target = tdee

    # Protein: 2.0 g/kg for endurance athletes
    protein_target = round(weight_kg * 2.0, 0)

    return {
        "target_calories":  int(cal_target),
        "target_protein_g": protein_target,
        "target_fasting_hrs": None,  # only set if explicitly requested
    }


def _upsert_plan_targets(db, user_id: int, targets: dict) -> None:
    from app.models.plan_targets import PlanTargets
    from datetime import date
    import uuid

    existing = (
        db.query(PlanTargets)
        .filter(PlanTargets.athlete_id == user_id)
        .order_by(PlanTargets.effective_from.desc())
        .first()
    )
    today = date.today()
    if existing and existing.effective_from == today:
        existing.target_calories  = targets.get("target_calories")
        existing.target_protein_g = targets.get("target_protein_g")
    else:
        db.add(PlanTargets(
            id=str(uuid.uuid4()),
            athlete_id=user_id,
            effective_from=today,
            target_calories=targets.get("target_calories"),
            target_protein_g=targets.get("target_protein_g"),
            target_fasting_hrs=targets.get("target_fasting_hrs"),
        ))
    db.commit()


async def _evaluate_progress(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Evaluate progress toward athlete goals using workout volume, weight trends,
    and goal targets. Returns per-goal trends, ETAs, and a coaching summary.
    """
    from app.ai.skills.progress_analyzer import ProgressAnalyzer
    from app.ai.skills.body_trend_analyzer import BodyTrendAnalyzer
    from app.ai.skills.coach_synthesizer import CoachSynthesizer
    from app.ai.skills.schemas import ProgressInput, BodyTrendInput, CoachInput

    goal_id = parameters.get("goal_id")
    lookback_weeks = int(parameters.get("lookback_weeks", 8))
    user_question = parameters.get("user_question", "")

    progress_report = await ProgressAnalyzer(db, user_id).run(ProgressInput(goal_id=goal_id))
    body_trend = await BodyTrendAnalyzer(db, user_id).run(BodyTrendInput(lookback_weeks=lookback_weeks))

    coach_response = await CoachSynthesizer(db, user_id).run(
        CoachInput(
            progress_report=progress_report,
            body_trend=body_trend,
            user_question=user_question,
        )
    )

    logger.info("evaluate_progress completed for user_id=%d", user_id)
    return {
        "success": True,
        "headline": coach_response.headline,
        "body": coach_response.body,
        "next_action": coach_response.next_action,
        "confidence": coach_response.confidence,
        "evidence_refs": coach_response.evidence_refs,
        "progress": {
            "overall_trend": progress_report.overall_trend,
            "summary": progress_report.summary,
            "goals": [
                {
                    "goal_id": g.goal_id,
                    "goal_type": g.goal_type,
                    "description": g.description,
                    "current_value": g.current_value,
                    "target_value": g.target_value,
                    "gap": g.gap,
                    "trend": g.trend,
                    "eta_weeks": g.eta_weeks,
                    "adjustment_suggested": g.adjustment_suggested,
                    "adjustment_note": g.adjustment_note,
                }
                for g in progress_report.goals
            ],
        },
        "body_trend": {
            "weeks_analysed": body_trend.weeks_analysed,
            "weight_slope_kg_per_week": body_trend.weight_slope_kg_per_week,
            "body_fat_trend": body_trend.body_fat_trend,
            "plateau_detected": body_trend.plateau_detected,
            "assessment": body_trend.assessment,
        },
    }


async def _fetch_strava_activity_detail(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Fetch a single activity's full detail from Strava and update the DB record.
    Use this when the athlete asks about a specific activity or when key fields
    (e.g. power, cadence) are missing from the summary record.
    """
    from app.services.strava_client import StravaClient

    strava_activity_id = parameters.get("strava_activity_id")
    if not strava_activity_id:
        raise ValueError("strava_activity_id parameter is required")

    strava_activity_id = int(strava_activity_id)

    client = StravaClient(db)
    data = await client.get_activity(user_id, strava_activity_id)

    # Update DB record with enriched data
    existing = db.query(StravaActivity).filter(
        StravaActivity.strava_id == strava_activity_id,
        StravaActivity.athlete_id == user_id,
    ).first()

    if existing:
        fields = StravaClient._map_activity_fields(user_id, data)
        for k, v in fields.items():
            if k not in ("athlete_id", "strava_id"):
                setattr(existing, k, v)
        db.commit()

    return {
        "success": True,
        "strava_id": strava_activity_id,
        "name": data.get("name"),
        "sport_type": data.get("sport_type") or data.get("type"),
        "start_date": data.get("start_date"),
        "moving_time_s": data.get("moving_time"),
        "distance_m": data.get("distance"),
        "elevation_m": data.get("total_elevation_gain"),
        "avg_hr": data.get("average_heartrate"),
        "max_hr": data.get("max_heartrate"),
        "avg_cadence": data.get("average_cadence"),
        "max_cadence": data.get("max_cadence"),
        "avg_watts": data.get("average_watts"),
        "weighted_avg_watts": data.get("weighted_average_watts"),
        "suffer_score": data.get("suffer_score"),
        "trainer": bool(data.get("trainer")),
        "description": data.get("description"),
        "db_updated": existing is not None,
    }


# Tool Definitions for LLM

async def _evaluate_performance_goal(
    parameters: Dict[str, Any],
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Estimate what a goal requires and how far the athlete is from it.

    Uses PerformanceEstimator (grounded in AthleteSportProfile) then
    CoachSynthesizer to produce a coaching response.

    Guardrail: never emits target_watts, W/kg, or FTP-derived targets.
    Only speed, distance, duration, and gap — all from real activities.
    """
    from app.ai.skills.performance_estimator import PerformanceEstimator
    from app.ai.skills.coach_synthesizer import CoachSynthesizer
    from app.ai.skills.schemas import PerformanceGoalInput, CoachInput

    goal_description = parameters.get("goal_description", "")
    sport_group      = parameters.get("sport_group")       # optional override
    user_question    = parameters.get("user_question", goal_description)

    estimate = await PerformanceEstimator(db, user_id).run(
        PerformanceGoalInput(query=goal_description, sport_group=sport_group)
    )

    coach_response = await CoachSynthesizer(db, user_id).run(
        CoachInput(
            performance_estimate=estimate,
            user_question=user_question,
        )
    )

    logger.info("evaluate_performance_goal completed for user_id=%d", user_id)
    return {
        "success": True,
        "headline":     coach_response.headline,
        "body":         coach_response.body,
        "next_action":  coach_response.next_action,
        "confidence":   coach_response.confidence,
        "evidence_refs": coach_response.evidence_refs,
        "performance_estimate": {
            "sport_group":                       estimate.sport_group,
            "target_distance_km":                estimate.target_distance_km,
            "target_duration_min":               estimate.target_duration_min,
            "target_speed_kmh":                  estimate.target_speed_kmh,
            "current_best_comparable_speed_kmh": estimate.current_best_comparable_speed_kmh,
            "speed_gap_kmh":                     estimate.speed_gap_kmh,
            "speed_gap_percent":                 estimate.speed_gap_percent,
            "comparable_basis":                  estimate.comparable_basis,
            "current_limiters":                  estimate.current_limiters,
            "data_basis":                        estimate.data_basis,
            "confidence":                        estimate.confidence,
            "parse_success":                     estimate.parse_success,
        },
    }


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
                'name': 'query_activities',
                'description': (
                    'Run a flexible query against the athlete\'s activity database. '
                    'Use for ANY question about activities: listing, ranking, filtering, counting, or computing stats. '
                    'Today\'s date is available in your context — use it to compute date ranges. '
                    'Call this tool immediately; do not ask the athlete for clarification first.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'filters': {
                            'type': 'array',
                            'description': (
                                'Filter conditions. Each filter: {field, op, value}. '
                                'Fields: sport_type, activity_type, distance_m, moving_time_s, '
                                'elevation_m, start_date (ISO 8601), avg_hr, max_hr, '
                                'calories, avg_watts, avg_cadence, suffer_score, trainer. '
                                'Ops: eq, ne, gt, gte, lt, lte, in, not_in.'
                            ),
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'field': {'type': 'string'},
                                    'op':    {'type': 'string'},
                                    'value': {},
                                },
                                'required': ['field', 'op', 'value'],
                            },
                        },
                        'sort': {
                            'type': 'array',
                            'description': (
                                'Sort order. Each entry: {field, dir}. '
                                'dir is "asc" or "desc". '
                                'Example: [{"field": "distance_m", "dir": "desc"}] → longest first.'
                            ),
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'field': {'type': 'string'},
                                    'dir':   {'type': 'string'},
                                },
                                'required': ['field'],
                            },
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Max activities to return (default 20, max 100).',
                            'default': 20,
                        },
                        'aggregate': {
                            'type': 'object',
                            'description': (
                                'Return aggregate stats instead of individual records. '
                                'metrics is a list of "fn:field" strings. '
                                'fn: count, sum, avg, max, min. '
                                'field: distance_m, moving_time_s, elevation_m, avg_hr, calories, avg_watts. '
                                'Example: {"metrics": ["count", "sum:distance_m", "max:distance_m"]}'
                            ),
                            'properties': {
                                'metrics': {'type': 'array', 'items': {'type': 'string'}},
                            },
                            'required': ['metrics'],
                        },
                    },
                    'required': [],
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
        },
        {
            'type': 'function',
            'function': {
                'name': 'analyze_recent_workout',
                'description': (
                    'Analyse the athlete\'s recent workout(s) using a structured evaluation '
                    'pipeline. Returns cadence quality, effort level, limiter hypothesis, '
                    'fatigue state (ACWR), and a focused coaching recommendation. '
                    'Use this whenever the athlete asks about their last ride/run/workout, '
                    'how they are performing, or what they should focus on.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'n_recent': {
                            'type': 'integer',
                            'description': 'Number of recent activities to analyse (default: 1)',
                            'default': 1
                        },
                        'strava_id': {
                            'type': 'integer',
                            'description': 'Optional: analyse a specific Strava activity by ID'
                        },
                        'user_question': {
                            'type': 'string',
                            'description': 'The athlete\'s original question to guide the coaching focus'
                        }
                    },
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'evaluate_recovery',
                'description': (
                    'Evaluate the athlete\'s current recovery and fatigue state using '
                    'Acute:Chronic Workload Ratio (ACWR) and resting heart rate trends. '
                    'Returns fatigue level, whether rest is recommended, and a specific '
                    'training recommendation. Use when the athlete asks about recovery, '
                    'if they should train today, or how tired they are.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'lookback_days': {
                            'type': 'integer',
                            'description': 'Days of history to analyse (default: 28)',
                            'default': 28
                        },
                        'user_question': {
                            'type': 'string',
                            'description': 'The athlete\'s original question to guide the coaching focus'
                        }
                    },
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'generate_plan',
                'description': (
                    'Generate a personalised training plan (and optionally nutrition targets) '
                    'grounded in the athlete\'s fitness state, goals, and recovery status. '
                    'Saves the plan to the database. '
                    'Use when the athlete asks to create a training plan, what they should do '
                    'this week/month, or for a structured programme.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'plan_type': {
                            'type': 'string',
                            'enum': ['training', 'nutrition', 'both'],
                            'description': 'What type of plan to generate (default: training)',
                            'default': 'training'
                        },
                        'duration_weeks': {
                            'type': 'integer',
                            'description': 'Length of the training plan in weeks (default: 4, max: 12)',
                            'default': 4
                        },
                        'goal_id': {
                            'type': 'string',
                            'description': 'Optional: link the plan to a specific goal by ID'
                        },
                        'user_question': {
                            'type': 'string',
                            'description': 'The athlete\'s original request to guide the plan focus'
                        }
                    },
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'evaluate_progress',
                'description': (
                    'Evaluate the athlete\'s progress toward their fitness goals. '
                    'Analyses weight trends, training volume, and goal gaps. '
                    'Returns per-goal trends, ETAs, and a coaching recommendation. '
                    'Use when the athlete asks about their progress, whether they\'re on track, '
                    'how far they are from their goal, or what needs to change.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'goal_id': {
                            'type': 'string',
                            'description': 'Optional: evaluate a specific goal by ID. Omit for all active goals.'
                        },
                        'lookback_weeks': {
                            'type': 'integer',
                            'description': 'Weeks of body measurement history to analyse (default: 8)',
                            'default': 8
                        },
                        'user_question': {
                            'type': 'string',
                            'description': 'The athlete\'s original question to guide coaching focus'
                        }
                    },
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'fetch_strava_activity_detail',
                'description': (
                    'Fetch full details for a specific Strava activity (power, cadence, HR, '
                    'description, etc.) and update the local database. Use this when a summary '
                    'record is missing key fields, or when the athlete references a specific '
                    'activity by name or date.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'strava_activity_id': {
                            'type': 'integer',
                            'description': 'The Strava activity ID to fetch'
                        }
                    },
                    'required': ['strava_activity_id']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'evaluate_performance_goal',
                'description': (
                    'Estimate what a specific performance goal requires and how far the athlete '
                    'currently is from achieving it. Use when the athlete asks things like: '
                    '"Can I ride 70 km in 3 hours?", "Am I ready for a marathon?", '
                    '"How much faster do I need to be?", "What do I need to achieve my goal?". '
                    'Returns target speed, current comparable speed, the gap, and coaching guidance. '
                    'Only uses grounded metrics from real activities — never predicts watts or FTP targets.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'goal_description': {
                            'type': 'string',
                            'description': (
                                'The athlete\'s goal in natural language. '
                                'Examples: "ride 70 km in 3 hours", "run a marathon in 4 hours", '
                                '"complete a century ride", "run 10 km in under 50 minutes".'
                            )
                        },
                        'sport_group': {
                            'type': 'string',
                            'enum': ['ride', 'run', 'swim', 'strength'],
                            'description': 'Optional: override sport detection if ambiguous.'
                        },
                        'user_question': {
                            'type': 'string',
                            'description': 'The athlete\'s original question to guide coaching tone.'
                        }
                    },
                    'required': ['goal_description']
                }
            }
        }
    ]
