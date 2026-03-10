"""Tests for Chat Tools

Tests the tool execution framework and all tool implementations.
Verifies user_id scoping, error handling, and tool functionality.
"""
import pytest
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.services.chat_tools import (
    execute_tool,
    get_tool_definitions,
    UserIdMissingError,
    ToolExecutionError,
    _save_athlete_goal,
    _get_my_goals,
    _get_my_recent_activities,
    _get_my_weekly_metrics,
    _save_training_plan,
    _get_training_plan,
    _search_web
)
from app.models.athlete_goal import AthleteGoal, GoalType, GoalStatus
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.database import get_db, engine
from app.models.base import Base


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


class TestToolExecutionFramework:
    """Test the tool execution framework (Task 7.1)"""
    
    @pytest.mark.asyncio
    async def test_execute_tool_requires_user_id(self, db_session: Session):
        """Test that execute_tool raises error when user_id is None"""
        with pytest.raises(UserIdMissingError) as exc_info:
            await execute_tool(
                tool_name="get_my_goals",
                parameters={},
                user_id=None,
                db=db_session
            )
        
        assert "user_id is required" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_tool_unknown_tool(self, db_session: Session):
        """Test that execute_tool raises error for unknown tool"""
        with pytest.raises(ToolExecutionError) as exc_info:
            await execute_tool(
                tool_name="unknown_tool",
                parameters={},
                user_id=1,
                db=db_session
            )
        
        assert "Unknown tool" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_tool_handles_exceptions(self, db_session: Session):
        """Test that execute_tool wraps exceptions in ToolExecutionError"""
        # Try to save goal with invalid parameters
        with pytest.raises(ToolExecutionError):
            await execute_tool(
                tool_name="save_athlete_goal",
                parameters={
                    'goal_type': 'invalid_type',
                    'description': 'Test'
                },
                user_id=1,
                db=db_session
            )
    
    @pytest.mark.asyncio
    async def test_execute_tool_routes_correctly(self, db_session: Session):
        """Test that execute_tool routes to correct tool implementation"""
        # Mock the tool implementation
        with patch('app.services.chat_tools._get_my_goals', new_callable=AsyncMock) as mock_tool:
            mock_tool.return_value = {'success': True, 'goals': []}
            
            result = await execute_tool(
                tool_name="get_my_goals",
                parameters={},
                user_id=1,
                db=db_session
            )
            
            assert result['success'] is True
            mock_tool.assert_called_once()


class TestAthleteGoalTools:
    """Test athlete goal tools (Task 7.2)"""
    
    @pytest.mark.asyncio
    async def test_save_athlete_goal(self, db_session: Session):
        """Test saving an athlete goal"""
        result = await _save_athlete_goal(
            parameters={
                'goal_type': 'weight_loss',
                'description': 'Lose 10kg for marathon training',
                'target_value': 75.0,
                'target_date': '2024-12-31'
            },
            user_id=1,
            db=db_session
        )
        
        assert result['success'] is True
        assert 'goal_id' in result
        
        # Verify goal was saved
        goal = db_session.query(AthleteGoal).filter(
            AthleteGoal.id == result['goal_id']
        ).first()
        
        assert goal is not None
        assert goal.athlete_id == '1'
        assert goal.goal_type == 'weight_loss'
        assert goal.target_value == 75.0
    
    @pytest.mark.asyncio
    async def test_save_athlete_goal_with_user_id_scoping(self, db_session: Session):
        """Test that save_athlete_goal uses user_id for scoping"""
        result = await _save_athlete_goal(
            parameters={
                'goal_type': 'performance',
                'description': 'Run sub-4 hour marathon'
            },
            user_id=42,
            db=db_session
        )
        
        goal = db_session.query(AthleteGoal).filter(
            AthleteGoal.id == result['goal_id']
        ).first()
        
        assert goal.athlete_id == '42'
    
    @pytest.mark.asyncio
    async def test_get_my_goals(self, db_session: Session):
        """Test retrieving athlete goals"""
        # Create test goals
        goal1 = AthleteGoal(
            id='goal-1',
            athlete_id='1',
            goal_type=GoalType.WEIGHT_LOSS.value,
            description='Test goal 1',
            status=GoalStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        goal2 = AthleteGoal(
            id='goal-2',
            athlete_id='1',
            goal_type=GoalType.PERFORMANCE.value,
            description='Test goal 2',
            status=GoalStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add_all([goal1, goal2])
        db_session.commit()
        
        result = await _get_my_goals(
            parameters={},
            user_id=1,
            db=db_session
        )
        
        assert result['success'] is True
        assert result['count'] == 2
        assert len(result['goals']) == 2
    
    @pytest.mark.asyncio
    async def test_get_my_goals_user_scoping(self, db_session: Session):
        """Test that get_my_goals only returns goals for the requesting user"""
        # Create goals for different users
        goal1 = AthleteGoal(
            id='goal-1',
            athlete_id='1',
            goal_type=GoalType.WEIGHT_LOSS.value,
            description='User 1 goal',
            status=GoalStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        goal2 = AthleteGoal(
            id='goal-2',
            athlete_id='2',
            goal_type=GoalType.PERFORMANCE.value,
            description='User 2 goal',
            status=GoalStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add_all([goal1, goal2])
        db_session.commit()
        
        # Query as user 1
        result = await _get_my_goals(
            parameters={},
            user_id=1,
            db=db_session
        )
        
        assert result['count'] == 1
        assert result['goals'][0]['description'] == 'User 1 goal'


class TestActivityAndMetricsTools:
    """Test activity and metrics tools (Task 7.3)"""
    
    @pytest.mark.asyncio
    async def test_get_my_recent_activities_default_days(self, db_session: Session):
        """Test retrieving recent activities with default 28 days"""
        # Create test activities
        now = datetime.now()
        activity1 = StravaActivity(
            athlete_id=1,
            strava_id=1001,
            activity_type='Run',
            start_date=now - timedelta(days=5),
            moving_time_s=3600,
            distance_m=10000,
            raw_json='{}'
        )
        activity2 = StravaActivity(
            athlete_id=1,
            strava_id=1002,
            activity_type='Ride',
            start_date=now - timedelta(days=30),  # Outside default range
            moving_time_s=7200,
            distance_m=50000,
            raw_json='{}'
        )
        db_session.add_all([activity1, activity2])
        db_session.commit()
        
        result = await _get_my_recent_activities(
            parameters={},
            user_id=1,
            db=db_session
        )
        
        assert result['success'] is True
        assert result['days'] == 28
        assert result['count'] == 1  # Only activity1 within 28 days
        assert result['activities'][0]['activity_type'] == 'Run'
    
    @pytest.mark.asyncio
    async def test_get_my_recent_activities_custom_days(self, db_session: Session):
        """Test retrieving recent activities with custom days parameter"""
        now = datetime.now()
        activity = StravaActivity(
            athlete_id=1,
            strava_id=1001,
            activity_type='Run',
            start_date=now - timedelta(days=10),
            moving_time_s=3600,
            distance_m=10000,
            raw_json='{}'
        )
        db_session.add(activity)
        db_session.commit()
        
        result = await _get_my_recent_activities(
            parameters={'days': 14},
            user_id=1,
            db=db_session
        )
        
        assert result['days'] == 14
        assert result['count'] == 1
    
    @pytest.mark.asyncio
    async def test_get_my_recent_activities_user_scoping(self, db_session: Session):
        """Test that activities are scoped to user_id"""
        now = datetime.now()
        activity1 = StravaActivity(
            athlete_id=1,
            strava_id=1001,
            activity_type='Run',
            start_date=now - timedelta(days=5),
            moving_time_s=3600,
            distance_m=10000,
            raw_json='{}'
        )
        activity2 = StravaActivity(
            athlete_id=2,
            strava_id=1002,
            activity_type='Ride',
            start_date=now - timedelta(days=5),
            moving_time_s=7200,
            distance_m=50000,
            raw_json='{}'
        )
        db_session.add_all([activity1, activity2])
        db_session.commit()
        
        result = await _get_my_recent_activities(
            parameters={},
            user_id=1,
            db=db_session
        )
        
        assert result['count'] == 1
        assert result['activities'][0]['activity_type'] == 'Run'
    
    @pytest.mark.asyncio
    async def test_get_my_weekly_metrics_default_weeks(self, db_session: Session):
        """Test retrieving weekly metrics with default 4 weeks"""
        # Create test data
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
        measurement = WeeklyMeasurement(
            week_id='2024-W10',
            week_start=week_start,
            avg_resting_hr=60,
            avg_weight_kg=75.0
        )
        db_session.add(measurement)
        
        activity = StravaActivity(
            athlete_id=1,
            strava_id=1001,
            activity_type='Run',
            start_date=datetime.combine(week_start, datetime.min.time()),
            moving_time_s=3600,
            distance_m=10000,
            raw_json='{}'
        )
        db_session.add(activity)
        db_session.commit()
        
        result = await _get_my_weekly_metrics(
            parameters={},
            user_id=1,
            db=db_session
        )
        
        assert result['success'] is True
        assert result['weeks'] == 4
        assert len(result['weekly_metrics']) >= 1
    
    @pytest.mark.asyncio
    async def test_get_my_weekly_metrics_custom_weeks(self, db_session: Session):
        """Test retrieving weekly metrics with custom weeks parameter"""
        result = await _get_my_weekly_metrics(
            parameters={'weeks': 8},
            user_id=1,
            db=db_session
        )
        
        assert result['weeks'] == 8


class TestTrainingPlanTools:
    """Test training plan tools (Task 7.4)"""
    
    @pytest.mark.asyncio
    async def test_save_training_plan(self, db_session: Session):
        """Test saving a training plan"""
        plan_text = """# Training Plan: Test Marathon Plan
Sport: running
Duration: 4 weeks
Start Date: 2024-01-01

## Week 1: Base Building
Volume Target: 30 hours

### Monday - Easy Run
Duration: 45 minutes
Intensity: easy
Description: Easy pace, focus on form

### Tuesday - Rest
Duration: 0 minutes
Intensity: recovery
Description: Rest day
"""
        
        with patch('app.services.chat_tools.LLMClient'):
            result = await _save_training_plan(
                parameters={'plan_text': plan_text},
                user_id=1,
                db=db_session
            )
        
        assert result['success'] is True
        assert 'plan_id' in result
    
    @pytest.mark.asyncio
    async def test_save_training_plan_requires_plan_text(self, db_session: Session):
        """Test that save_training_plan requires plan_text parameter"""
        with pytest.raises(ValueError) as exc_info:
            await _save_training_plan(
                parameters={},
                user_id=1,
                db=db_session
            )
        
        assert "plan_text parameter is required" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_training_plan(self, db_session: Session):
        """Test retrieving a training plan"""
        # First save a plan
        plan_text = """# Training Plan: Test Plan
Sport: running
Duration: 2 weeks
Start Date: 2024-01-01

## Week 1: Base
Volume Target: 20 hours

### Monday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Easy run
"""
        
        with patch('app.services.chat_tools.LLMClient'):
            save_result = await _save_training_plan(
                parameters={'plan_text': plan_text},
                user_id=1,
                db=db_session
            )
            
            plan_id = save_result['plan_id']
            
            # Now retrieve it
            result = await _get_training_plan(
                parameters={'plan_id': plan_id},
                user_id=1,
                db=db_session
            )
        
        assert result['success'] is True
        assert result['plan_id'] == plan_id
        assert 'plan_text' in result
    
    @pytest.mark.asyncio
    async def test_get_training_plan_user_scoping(self, db_session: Session):
        """Test that get_training_plan enforces user_id scoping"""
        # Save plan as user 1
        plan_text = """# Training Plan: Test Plan
Sport: running
Duration: 2 weeks
Start Date: 2024-01-01

## Week 1: Base
Volume Target: 20 hours

### Monday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Easy run
"""
        
        with patch('app.services.chat_tools.LLMClient'):
            save_result = await _save_training_plan(
                parameters={'plan_text': plan_text},
                user_id=1,
                db=db_session
            )
            
            plan_id = save_result['plan_id']
            
            # Try to retrieve as user 2
            result = await _get_training_plan(
                parameters={'plan_id': plan_id},
                user_id=2,
                db=db_session
            )
        
        assert result['success'] is False
        assert "not found" in result['message']


class TestWebSearchTool:
    """Test web search tool (Task 7.5)"""
    
    @pytest.mark.asyncio
    async def test_search_web_success(self, db_session: Session):
        """Test successful web search with results and citations"""
        mock_response = {
            'answer': 'Marathon training typically takes 16-20 weeks',
            'results': [
                {
                    'title': 'Marathon Training Guide',
                    'url': 'https://example.com/marathon',
                    'content': 'Training content...',
                    'score': 0.95
                },
                {
                    'title': 'Running Science',
                    'url': 'https://example.com/science',
                    'content': 'Scientific approach to training',
                    'score': 0.88
                }
            ]
        }
        
        with patch('app.services.chat_tools.get_settings') as mock_settings:
            mock_settings.return_value.TAVILY_API_KEY = 'test-key'
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=Mock(
                        raise_for_status=Mock(),
                        json=Mock(return_value=mock_response)
                    )
                )
                
                result = await _search_web(
                    parameters={'query': 'marathon training duration'},
                    user_id=1,
                    db=db_session
                )
        
        assert result['success'] is True
        assert result['query'] == 'marathon training duration'
        assert result['answer'] == 'Marathon training typically takes 16-20 weeks'
        assert len(result['results']) == 2
        assert len(result['sources']) == 2
        assert 'https://example.com/marathon' in result['sources']
        assert 'https://example.com/science' in result['sources']
        
        # Verify result structure includes citations
        assert result['results'][0]['title'] == 'Marathon Training Guide'
        assert result['results'][0]['url'] == 'https://example.com/marathon'
        assert result['results'][0]['score'] == 0.95
    
    @pytest.mark.asyncio
    async def test_search_web_requires_api_key(self, db_session: Session):
        """Test that search_web requires Tavily API key"""
        with patch('app.services.chat_tools.get_settings') as mock_settings:
            mock_settings.return_value.TAVILY_API_KEY = ''
            
            with pytest.raises(ToolExecutionError) as exc_info:
                await _search_web(
                    parameters={'query': 'test query'},
                    user_id=1,
                    db=db_session
                )
            
            assert "API key not configured" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_search_web_requires_query(self, db_session: Session):
        """Test that search_web requires query parameter"""
        with patch('app.services.chat_tools.get_settings') as mock_settings:
            mock_settings.return_value.TAVILY_API_KEY = 'test-key'
            
            with pytest.raises(ValueError) as exc_info:
                await _search_web(
                    parameters={},
                    user_id=1,
                    db=db_session
                )
            
            assert "query parameter is required" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_search_web_handles_api_error(self, db_session: Session):
        """Test that search_web handles API errors gracefully"""
        import httpx
        
        with patch('app.services.chat_tools.get_settings') as mock_settings:
            mock_settings.return_value.TAVILY_API_KEY = 'test-key'
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_post = AsyncMock()
                mock_post.side_effect = httpx.HTTPStatusError(
                    "API Error",
                    request=Mock(),
                    response=Mock(status_code=500)
                )
                mock_client.return_value.__aenter__.return_value.post = mock_post
                
                with pytest.raises(httpx.HTTPStatusError):
                    await _search_web(
                        parameters={'query': 'test query'},
                        user_id=1,
                        db=db_session
                    )
    
    @pytest.mark.asyncio
    async def test_search_web_handles_timeout(self, db_session: Session):
        """Test that search_web handles timeout errors"""
        import httpx
        
        with patch('app.services.chat_tools.get_settings') as mock_settings:
            mock_settings.return_value.TAVILY_API_KEY = 'test-key'
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_post = AsyncMock()
                mock_post.side_effect = httpx.TimeoutException("Request timeout")
                mock_client.return_value.__aenter__.return_value.post = mock_post
                
                with pytest.raises(httpx.TimeoutException):
                    await _search_web(
                        parameters={'query': 'test query'},
                        user_id=1,
                        db=db_session
                    )
    
    @pytest.mark.asyncio
    async def test_search_web_empty_results(self, db_session: Session):
        """Test search_web with no results"""
        mock_response = {
            'answer': None,
            'results': []
        }
        
        with patch('app.services.chat_tools.get_settings') as mock_settings:
            mock_settings.return_value.TAVILY_API_KEY = 'test-key'
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=Mock(
                        raise_for_status=Mock(),
                        json=Mock(return_value=mock_response)
                    )
                )
                
                result = await _search_web(
                    parameters={'query': 'obscure query with no results'},
                    user_id=1,
                    db=db_session
                )
        
        assert result['success'] is True
        assert result['query'] == 'obscure query with no results'
        assert result['answer'] is None
        assert len(result['results']) == 0
        assert len(result['sources']) == 0
    
    @pytest.mark.asyncio
    async def test_search_web_user_id_scoping(self, db_session: Session):
        """Test that search_web respects user_id scoping"""
        mock_response = {
            'answer': 'Test answer',
            'results': [
                {
                    'title': 'Test',
                    'url': 'https://example.com',
                    'content': 'Content',
                    'score': 0.9
                }
            ]
        }
        
        with patch('app.services.chat_tools.get_settings') as mock_settings:
            mock_settings.return_value.TAVILY_API_KEY = 'test-key'
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=Mock(
                        raise_for_status=Mock(),
                        json=Mock(return_value=mock_response)
                    )
                )
                
                # Execute search for user 1
                result1 = await _search_web(
                    parameters={'query': 'test query'},
                    user_id=1,
                    db=db_session
                )
                
                # Execute search for user 2
                result2 = await _search_web(
                    parameters={'query': 'test query'},
                    user_id=2,
                    db=db_session
                )
        
        # Both should succeed - user_id is used for logging/auditing
        assert result1['success'] is True
        assert result2['success'] is True


class TestToolDefinitions:
    """Test tool definitions for LLM"""
    
    def test_get_tool_definitions_returns_all_tools(self):
        """Test that get_tool_definitions returns all 7 tools"""
        definitions = get_tool_definitions()
        
        assert len(definitions) == 7
        
        tool_names = [d['function']['name'] for d in definitions]
        assert 'save_athlete_goal' in tool_names
        assert 'get_my_goals' in tool_names
        assert 'get_my_recent_activities' in tool_names
        assert 'get_my_weekly_metrics' in tool_names
        assert 'save_training_plan' in tool_names
        assert 'get_training_plan' in tool_names
        assert 'search_web' in tool_names
    
    def test_tool_definitions_have_required_fields(self):
        """Test that all tool definitions have required fields"""
        definitions = get_tool_definitions()
        
        for definition in definitions:
            assert 'type' in definition
            assert definition['type'] == 'function'
            assert 'function' in definition
            
            function = definition['function']
            assert 'name' in function
            assert 'description' in function
            assert 'parameters' in function
            
            parameters = function['parameters']
            assert 'type' in parameters
            assert 'properties' in parameters
            assert 'required' in parameters
