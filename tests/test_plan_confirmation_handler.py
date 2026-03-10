"""Tests for Plan Confirmation Handler

Tests plan generation flow with confirmation and modification.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import date

from app.services.plan_confirmation_handler import (
    PlanConfirmationHandler,
    PlanState
)
from app.schemas.training_plan import TrainingPlan, TrainingWeek, TrainingSession


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    return Mock()


@pytest.fixture
def mock_plan():
    """Create a mock training plan."""
    return TrainingPlan(
        id=None,
        user_id=1,
        title="12-Week Marathon Training",
        sport="running",
        goal_id="goal-123",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 24),
        status="draft",
        weeks=[
            TrainingWeek(
                week_number=1,
                focus="Base building",
                volume_target=20.0,
                sessions=[
                    TrainingSession(
                        day_of_week=1,
                        session_type="easy_run",
                        duration_minutes=45,
                        intensity="easy",
                        description="Easy pace run"
                    )
                ]
            )
        ]
    )


@pytest.fixture
def handler(mock_db, mock_llm_client):
    """Create plan confirmation handler."""
    return PlanConfirmationHandler(db=mock_db, llm_client=mock_llm_client)


@pytest.mark.asyncio
async def test_generate_and_present_plan(handler, mock_plan):
    """Test generating and presenting a plan."""
    # Mock plan engine
    with patch.object(handler.plan_engine, 'generate_plan', new_callable=AsyncMock) as mock_generate:
        with patch.object(handler.plan_engine, 'pretty_print') as mock_print:
            mock_generate.return_value = mock_plan
            mock_print.return_value = "# Training Plan..."
            
            # Generate and present
            result = await handler.generate_and_present_plan(
                user_id=1,
                session_id=42,
                sport="running",
                duration_weeks=12,
                goal_description="Sub-4 hour marathon"
            )
            
            # Verify result
            assert result['success'] is True
            assert result['plan'] == mock_plan
            assert result['state'] == PlanState.AWAITING_CONFIRMATION.value
            assert 'presentation' in result
            assert 'confirm' in result['presentation'].lower()
            
            # Verify pending plan stored
            assert handler.has_pending_plan(1, 42)


@pytest.mark.asyncio
async def test_handle_confirmation_save(handler, mock_plan):
    """Test handling confirmation to save plan."""
    # Set up pending plan
    handler.pending_plans["1:42"] = {
        'plan': mock_plan,
        'state': PlanState.AWAITING_CONFIRMATION,
        'user_id': 1,
        'session_id': 42
    }
    
    # Mock save
    with patch.object(handler.plan_engine, 'save_plan') as mock_save:
        mock_save.return_value = "plan-123"
        
        # Handle confirmation
        result = await handler.handle_confirmation_response(
            user_id=1,
            session_id=42,
            response="confirm"
        )
        
        # Verify result
        assert result['success'] is True
        assert result['action'] == 'saved'
        assert result['plan_id'] == "plan-123"
        assert 'saved' in result['message'].lower()
        
        # Verify pending plan removed
        assert not handler.has_pending_plan(1, 42)


@pytest.mark.asyncio
async def test_handle_confirmation_various_keywords(handler, mock_plan):
    """Test that various confirmation keywords work."""
    confirmation_keywords = ['confirm', 'save', 'yes', 'looks good', 'perfect']
    
    for keyword in confirmation_keywords:
        # Set up pending plan
        handler.pending_plans["1:42"] = {
            'plan': mock_plan,
            'state': PlanState.AWAITING_CONFIRMATION,
            'user_id': 1,
            'session_id': 42
        }
        
        # Mock save
        with patch.object(handler.plan_engine, 'save_plan') as mock_save:
            mock_save.return_value = "plan-123"
            
            # Handle confirmation
            result = await handler.handle_confirmation_response(
                user_id=1,
                session_id=42,
                response=keyword
            )
            
            # Verify saved
            assert result['success'] is True
            assert result['action'] == 'saved'


@pytest.mark.asyncio
async def test_handle_modification_request(handler, mock_plan):
    """Test handling modification request."""
    # Set up pending plan
    handler.pending_plans["1:42"] = {
        'plan': mock_plan,
        'state': PlanState.AWAITING_CONFIRMATION,
        'user_id': 1,
        'session_id': 42
    }
    
    # Mock iteration
    modified_plan = mock_plan
    modified_plan.title = "Modified Plan"
    
    with patch.object(handler.plan_engine, 'iterate_plan', new_callable=AsyncMock) as mock_iterate:
        with patch('app.services.plan_confirmation_handler.TrainingPlanEngine.pretty_print') as mock_print:
            mock_iterate.return_value = modified_plan
            mock_print.return_value = "# Modified Plan..."
            
            # Handle modification
            result = await handler.handle_confirmation_response(
                user_id=1,
                session_id=42,
                response="modify - add more rest days"
            )
            
            # Verify result
            assert result['success'] is True
            assert result['action'] == 'modified'
            assert result['plan'] == modified_plan
            assert 'presentation' in result
            
            # Verify iterate_plan was called
            mock_iterate.assert_called_once()
            
            # Verify pending plan updated
            assert handler.has_pending_plan(1, 42)
            assert handler.get_pending_plan(1, 42) == modified_plan


@pytest.mark.asyncio
async def test_handle_regeneration_request(handler, mock_plan):
    """Test handling regeneration request."""
    # Set up pending plan
    handler.pending_plans["1:42"] = {
        'plan': mock_plan,
        'state': PlanState.AWAITING_CONFIRMATION,
        'user_id': 1,
        'session_id': 42
    }
    
    # Handle regeneration
    result = await handler.handle_confirmation_response(
        user_id=1,
        session_id=42,
        response="regenerate"
    )
    
    # Verify result
    assert result['success'] is True
    assert result['action'] == 'regenerate'
    assert 'new plan' in result['message'].lower()


@pytest.mark.asyncio
async def test_handle_unclear_response(handler, mock_plan):
    """Test handling unclear response."""
    # Set up pending plan
    handler.pending_plans["1:42"] = {
        'plan': mock_plan,
        'state': PlanState.AWAITING_CONFIRMATION,
        'user_id': 1,
        'session_id': 42
    }
    
    # Handle unclear response
    result = await handler.handle_confirmation_response(
        user_id=1,
        session_id=42,
        response="I don't know"
    )
    
    # Verify result
    assert result['success'] is False
    assert result['action'] == 'unclear'
    assert 'not sure' in result['message'].lower()


@pytest.mark.asyncio
async def test_handle_response_no_pending_plan(handler):
    """Test handling response when no pending plan exists."""
    # Handle response without pending plan
    result = await handler.handle_confirmation_response(
        user_id=1,
        session_id=42,
        response="confirm"
    )
    
    # Verify error
    assert result['success'] is False
    assert 'no pending plan' in result['message'].lower()


def test_extract_modification_request(handler):
    """Test extracting modification request from response."""
    # Test various formats
    assert "add more rest days" in handler._extract_modification_request(
        "modify - add more rest days"
    )
    
    assert "reduce intensity" in handler._extract_modification_request(
        "change: reduce intensity in week 3"
    )
    
    assert "longer runs" in handler._extract_modification_request(
        "can you please adjust to include longer runs"
    )


def test_has_pending_plan(handler, mock_plan):
    """Test checking for pending plan."""
    # No pending plan
    assert handler.has_pending_plan(1, 42) is False
    
    # Add pending plan
    handler.pending_plans["1:42"] = {
        'plan': mock_plan,
        'state': PlanState.AWAITING_CONFIRMATION,
        'user_id': 1,
        'session_id': 42
    }
    
    # Has pending plan
    assert handler.has_pending_plan(1, 42) is True


def test_get_pending_plan(handler, mock_plan):
    """Test getting pending plan."""
    # No pending plan
    assert handler.get_pending_plan(1, 42) is None
    
    # Add pending plan
    handler.pending_plans["1:42"] = {
        'plan': mock_plan,
        'state': PlanState.AWAITING_CONFIRMATION,
        'user_id': 1,
        'session_id': 42
    }
    
    # Get pending plan
    plan = handler.get_pending_plan(1, 42)
    assert plan == mock_plan


def test_clear_pending_plan(handler, mock_plan):
    """Test clearing pending plan."""
    # Add pending plan
    handler.pending_plans["1:42"] = {
        'plan': mock_plan,
        'state': PlanState.AWAITING_CONFIRMATION,
        'user_id': 1,
        'session_id': 42
    }
    
    # Clear pending plan
    handler.clear_pending_plan(1, 42)
    
    # Verify cleared
    assert handler.has_pending_plan(1, 42) is False


def test_format_plan_presentation(handler, mock_plan):
    """Test formatting plan presentation."""
    plan_text = "# Training Plan\n## Week 1..."
    
    presentation = handler._format_plan_presentation(mock_plan, plan_text)
    
    # Verify presentation includes key elements
    assert mock_plan.title in presentation
    assert mock_plan.sport in presentation.lower()
    assert 'confirm' in presentation.lower()
    assert 'modify' in presentation.lower()
    assert plan_text in presentation
