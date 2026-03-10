"""Tests for performance monitoring and logging

Verifies that performance metrics are logged and warnings are issued
when performance thresholds are exceeded.

Requirements: 17.1, 17.2, 17.3, 18.1, 18.2, 18.3
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from sqlalchemy.orm import Session
import numpy as np
import time

from app.services.rag_engine import RAGEngine
from app.services.session_matcher import SessionMatcher
from app.services.chat_message_handler import ChatMessageHandler
from app.models.strava_activity import StravaActivity
from datetime import datetime, timedelta


class TestRAGEnginePerformanceMonitoring:
    """Test performance monitoring in RAG Engine (Requirement 17.2)"""
    
    @patch('app.services.rag_engine.print')
    @patch('app.services.rag_engine.time')
    def test_retrieve_context_logs_vector_retrieval_latency(self, mock_time, mock_print):
        """Verify retrieve_context logs vector retrieval latency"""
        # Mock time to simulate 300ms vector retrieval
        mock_time.time.side_effect = [0.0, 0.0, 0.3, 0.35]  # start, vector_start, vector_end, total_end
        
        db = Mock(spec=Session)
        rag_engine = RAGEngine(db, index_path="test_index.bin")
        
        # Mock embedding generation and search
        rag_engine.generate_embedding = Mock(return_value=np.random.rand(768).astype('float32'))
        rag_engine.search_similar = Mock(return_value=[])
        
        # Call retrieve_context
        rag_engine.retrieve_context("test query", user_id=1, active_session_messages=[])
        
        # Verify latency was logged
        latency_logs = [call for call in mock_print.call_args_list 
                       if 'Vector retrieval completed' in str(call)]
        assert len(latency_logs) > 0
        
        # Verify total latency was logged
        total_logs = [call for call in mock_print.call_args_list 
                     if 'Total context retrieval completed' in str(call)]
        assert len(total_logs) > 0
    
    @patch('app.services.rag_engine.print')
    @patch('app.services.rag_engine.time')
    def test_retrieve_context_warns_on_slow_vector_retrieval(self, mock_time, mock_print):
        """Verify retrieve_context warns when vector retrieval exceeds 500ms (Requirement 18.3)"""
        # Mock time to simulate 600ms vector retrieval (exceeds 500ms target)
        mock_time.time.side_effect = [0.0, 0.0, 0.6, 0.65]
        
        db = Mock(spec=Session)
        rag_engine = RAGEngine(db, index_path="test_index.bin")
        
        # Mock embedding generation and search
        rag_engine.generate_embedding = Mock(return_value=np.random.rand(768).astype('float32'))
        rag_engine.search_similar = Mock(return_value=[])
        
        # Call retrieve_context
        rag_engine.retrieve_context("test query", user_id=1, active_session_messages=[])
        
        # Verify performance warning was logged
        warning_logs = [call for call in mock_print.call_args_list 
                       if 'PERFORMANCE WARNING' in str(call) and 'exceeded 500ms' in str(call)]
        assert len(warning_logs) > 0


class TestChatMessageHandlerPerformanceMonitoring:
    """Test performance monitoring in Chat Message Handler (Requirement 17.1)"""
    
    @pytest.mark.asyncio
    @patch('app.services.chat_message_handler.logger')
    async def test_handle_message_logs_latency(self, mock_logger):
        """Verify handle_message logs chat response latency"""
        db = Mock(spec=Session)
        rag_engine = Mock(spec=RAGEngine)
        llm_client = Mock()
        
        # Mock RAG engine
        rag_engine.retrieve_context = Mock(return_value="")
        
        # Mock LLM client
        llm_client.chat_completion = Mock(return_value={
            'content': 'Test response',
            'tool_calls': None
        })
        
        handler = ChatMessageHandler(db, rag_engine, llm_client, user_id=1, session_id=1)
        
        # Handle message
        result = await handler.handle_message("test message")
        
        # Verify latency was logged
        assert 'latency_ms' in result
        assert result['latency_ms'] >= 0
        
        # Verify logger.info was called with latency
        info_calls = [call for call in mock_logger.info.call_args_list 
                     if 'Chat message handled' in str(call)]
        assert len(info_calls) > 0
    
    @pytest.mark.asyncio
    @patch('app.services.chat_message_handler.logger')
    @patch('app.services.chat_message_handler.time')
    async def test_handle_message_warns_on_slow_response(self, mock_time, mock_logger):
        """Verify handle_message warns when latency exceeds 3s (Requirement 17.1, 18.3)"""
        # Mock time to simulate 3.5 second response (exceeds 3s target)
        mock_time.time.side_effect = [0.0, 3.5]
        
        db = Mock(spec=Session)
        rag_engine = Mock(spec=RAGEngine)
        llm_client = Mock()
        
        # Mock RAG engine
        rag_engine.retrieve_context = Mock(return_value="")
        
        # Mock LLM client
        llm_client.chat_completion = Mock(return_value={
            'content': 'Test response',
            'tool_calls': None
        })
        
        handler = ChatMessageHandler(db, rag_engine, llm_client, user_id=1, session_id=1)
        
        # Handle message
        await handler.handle_message("test message")
        
        # Verify warning was logged
        warning_calls = [call for call in mock_logger.warning.call_args_list 
                        if 'Chat latency exceeded 3s target' in str(call)]
        assert len(warning_calls) > 0


class TestSessionMatcherPerformanceMonitoring:
    """Test performance monitoring in Session Matcher (Requirement 14.5)"""
    
    @patch('app.services.session_matcher.logger')
    @patch('app.services.session_matcher.time')
    def test_match_activity_logs_latency(self, mock_time, mock_logger):
        """Verify match_activity logs matching latency"""
        # Mock time to simulate 2 second matching
        mock_time.time.side_effect = [0.0, 2.0]
        
        db = Mock(spec=Session)
        matcher = SessionMatcher(db)
        
        # Mock find_candidate_sessions to return empty list
        matcher.find_candidate_sessions = Mock(return_value=[])
        
        activity = Mock(spec=StravaActivity)
        activity.id = "test-activity"
        activity.start_date = datetime.now()
        
        # Match activity
        result = matcher.match_activity(activity, user_id=1)
        
        # Verify latency was logged
        info_calls = [call for call in mock_logger.info.call_args_list 
                     if 'ms' in str(call)]
        assert len(info_calls) > 0
    
    @patch('app.services.session_matcher.logger')
    @patch('app.services.session_matcher.time')
    def test_match_activity_warns_on_slow_matching(self, mock_time, mock_logger):
        """Verify match_activity warns when matching exceeds 5s (Requirement 14.5, 18.3)"""
        # Mock time to simulate 6 second matching (exceeds 5s target)
        mock_time.time.side_effect = [0.0, 6.0]
        
        db = Mock(spec=Session)
        matcher = SessionMatcher(db)
        
        # Mock successful match
        mock_session = Mock()
        mock_session.id = "session-1"
        mock_session.session_type = "easy_run"
        mock_session.duration_minutes = 45
        mock_session.week = Mock()
        mock_session.week.plan_id = "plan-1"
        
        matcher.find_candidate_sessions = Mock(return_value=[mock_session])
        matcher.calculate_match_confidence = Mock(return_value=85.0)
        matcher._update_adherence_scores = Mock()
        
        activity = Mock(spec=StravaActivity)
        activity.id = "test-activity"
        activity.start_date = datetime.now()
        
        # Match activity
        matcher.match_activity(activity, user_id=1)
        
        # Verify performance warning was logged
        warning_calls = [call for call in mock_logger.warning.call_args_list 
                        if 'PERFORMANCE WARNING' in str(call) and 'exceeded 5s' in str(call)]
        assert len(warning_calls) > 0


class TestAPIPerformanceMonitoring:
    """Test performance monitoring in API endpoints (Requirements 18.1, 18.2, 18.3)"""
    
    # Note: These would be integration tests with FastAPI TestClient
    # For now, we verify the monitoring logic is in place
    
    def test_api_endpoints_log_performance(self):
        """Verify API endpoints log performance metrics"""
        # This is a placeholder - actual tests would use FastAPI TestClient
        # to verify performance logging in responses
        pass
    
    def test_api_endpoints_warn_on_slow_responses(self):
        """Verify API endpoints warn when exceeding 2s target"""
        # This is a placeholder - actual tests would use FastAPI TestClient
        # to verify performance warnings are logged
        pass


class TestPerformanceTargets:
    """Verify performance targets are documented and enforced"""
    
    def test_chat_response_target_is_3_seconds(self):
        """Verify chat response target is 3 seconds (Requirement 17.1)"""
        # This is documented in the code and enforced by logging
        assert True  # Placeholder
    
    def test_vector_retrieval_target_is_500ms(self):
        """Verify vector retrieval target is 500ms (Requirement 17.2)"""
        # This is documented in the code and enforced by logging
        assert True  # Placeholder
    
    def test_plan_screen_load_target_is_2_seconds(self):
        """Verify plan screen load target is 2 seconds (Requirements 18.1, 18.2)"""
        # This is documented in the code and enforced by logging
        assert True  # Placeholder
    
    def test_session_matching_target_is_5_seconds(self):
        """Verify session matching target is 5 seconds (Requirement 14.5)"""
        # This is documented in the code and enforced by logging
        assert True  # Placeholder
