# Implementation Plan: Fitness Platform Chat & Training Upgrade

## Overview

This implementation plan breaks down the fitness platform upgrade into three major components:

1. **Context-Engineered Chat**: Two-layer RAG-based retrieval system with active session buffer and vector store
2. **Training Plan Engine**: AI-powered generation, parsing, storage, and iteration of personalized training plans
3. **Plan Progress Screen**: Visual tracking interface with automatic Strava sync and adherence scoring

The implementation follows an incremental approach, building core infrastructure first, then adding intelligence layers, and finally integrating the UI components.

## Tasks

- [x] 1. Set up database schema and migrations
  - Create training_plans, training_plan_weeks, and training_plan_sessions tables
  - Add user_id column to faiss_metadata table for user-scoped vector queries
  - Create indexes for performance optimization
  - Apply row-level security policies
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 16.1, 16.2, 16.3, 16.4_

- [x] 2. Implement core data models and validation
  - [x] 2.1 Create SQLAlchemy models for training plans
    - Implement TrainingPlan, TrainingPlanWeek, TrainingPlanSession models
    - Add relationships and foreign key constraints
    - Implement validation methods for data integrity
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 2.2 Create Python dataclasses for training plan structures
    - Implement TrainingSession, TrainingWeek, TrainingPlan dataclasses
    - Add validation logic for session types, intensities, and durations
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 3. Implement RAG Engine with two-layer context retrieval
  - [x] 3.1 Create RAGEngine class with FAISS integration
    - Initialize FAISS index with nomic-embed-text embeddings (768-dim)
    - Implement user-scoped vector search with user_id filtering
    - Add metadata storage in SQLite with FaissMetadata table
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 20.1_

  - [x] 3.2 Implement active session buffer management
    - Create in-memory buffer for current session messages
    - Implement buffer retrieval and clearing logic
    - _Requirements: 1.1, 1.3_

  - [x] 3.3 Implement context retrieval algorithm
    - Combine active session buffer and vector store results
    - Format context for LLM consumption
    - Ensure p95 latency < 500ms for vector retrieval
    - _Requirements: 1.1, 1.2, 1.3, 17.2_

  - [x] 3.4 Implement session persistence to vector store
    - Generate embeddings for session messages
    - Store with key format: chat:{user_id}:{session_id}:{date}:eval_{score}
    - Add to FAISS index and metadata table
    - _Requirements: 1.4, 1.5, 1.6_

  - [x] 3.5 Implement session deletion
    - Remove session from vector store and database
    - Complete deletion within 2 seconds
    - Handle errors gracefully with logging
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 4. Implement Training Plan Parser and Pretty-Printer
  - [x] 4.1 Create plan parser for AI-generated text
    - Parse plan header (title, sport, duration, start date)
    - Parse week structures with focus and volume targets
    - Parse session details (day, type, duration, intensity, description)
    - Return structured TrainingPlan object
    - Raise ValueError for invalid formats with descriptive messages
    - _Requirements: 19.1, 19.2_

  - [x] 4.2 Create plan pretty-printer
    - Format TrainingPlan object to human-readable markdown
    - Ensure round-trip property: parse(print(plan)) produces equivalent object
    - _Requirements: 19.3, 19.4_

- [ ] 5. Checkpoint - Verify core data structures
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Training Plan Engine
  - [x] 6.1 Create TrainingPlanEngine class
    - Initialize with database session and LLM client
    - Implement save_plan method with database persistence
    - Implement get_plan method with user_id scoping
    - Implement list_plans method for user's plans
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 20.2_

  - [x] 6.2 Implement activity-aware plan generation
    - Retrieve recent activities using get_my_recent_activities
    - Retrieve weekly metrics using get_my_weekly_metrics
    - Incorporate activity data into LLM generation prompts
    - Generate plans with progressive volume increases
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 6.3 Implement plan-goal linking
    - Accept goal_id parameter in plan generation
    - Store goal_id in training_plans table
    - Include goal information in plan retrieval
    - Handle goal deletion with SET NULL
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 6.4 Implement plan iteration support
    - Retrieve existing plan using get_training_plan
    - Present current plan details to athlete
    - Generate updated plan incorporating modifications
    - Save updated plan on confirmation
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 7. Implement Chat Tools for LLM
  - [x] 7.1 Create tool execution framework
    - Implement execute_tool function with user_id scoping
    - Add validation for user_id presence
    - Add error handling and logging
    - _Requirements: 6.7, 20.3_

  - [x] 7.2 Implement athlete goal tools
    - Create save_athlete_goal tool
    - Create get_my_goals tool
    - _Requirements: 6.1, 6.2_

  - [x] 7.3 Implement activity and metrics tools
    - Create get_my_recent_activities tool with days parameter
    - Create get_my_weekly_metrics tool with weeks parameter
    - _Requirements: 6.3, 6.4_

  - [x] 7.4 Implement training plan tools
    - Create save_training_plan tool
    - Create get_training_plan tool
    - _Requirements: 6.5, 6.6_

  - [x] 7.5 Implement web search tool
    - Create search_web tool using Tavily API
    - Include source citations in results
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 8. Implement multi-step tool orchestration
  - [x] 8.1 Create chat message handler with tool support
    - Retrieve context from active buffer and vector store
    - Generate initial LLM response with tool definitions
    - Execute tools sequentially when requested
    - Pass tool results to subsequent tool calls
    - Generate final response incorporating all tool results
    - Ensure p95 latency < 3 seconds
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 17.1_

  - [x] 8.2 Implement clarification request logic
    - Detect low-confidence user intent
    - Generate clarification questions with specific options
    - Process original request with additional context
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 8.3 Implement plan generation flow with confirmation
    - Present generated plan to athlete for review
    - Wait for athlete confirmation before saving
    - Regenerate plan on modification requests
    - Save plan on confirmation
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 9. Checkpoint - Verify chat and plan generation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement Session Matcher for automatic activity matching
  - [x] 10.1 Create SessionMatcher class
    - Initialize with database session
    - Implement find_candidate_sessions method
    - Query unmatched sessions within 24 hours of activity
    - Filter by user_id and active plan status
    - _Requirements: 14.1, 20.2_

  - [x] 10.2 Implement match confidence calculation
    - Calculate time proximity score (40 points max)
    - Calculate sport type match score (30 points max)
    - Calculate duration similarity score (20 points max)
    - Calculate intensity alignment score (10 points max)
    - Return total confidence score 0-100
    - _Requirements: 14.2_

  - [x] 10.3 Implement activity matching logic
    - Find candidate sessions for new activity
    - Calculate confidence for each candidate
    - Update session if confidence > 80%
    - Set completed=true and matched_activity_id
    - Leave unmatched if confidence <= 80%
    - Complete processing within 5 seconds
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [x] 11. Implement adherence score calculations
  - [x] 11.1 Create adherence calculation functions
    - Implement calculate_session_adherence (100% if completed, 0% otherwise)
    - Implement calculate_week_adherence (percentage of completed sessions)
    - Implement calculate_plan_adherence (overall percentage)
    - Implement get_adherence_time_series for charting
    - _Requirements: 15.1, 15.2, 15.3_

  - [x] 11.2 Integrate adherence updates with session matching
    - Trigger adherence recalculation after session matching
    - Update adherence scores within 10 seconds
    - _Requirements: 15.4_

- [x] 12. Implement Training Plan API endpoints
  - [x] 12.1 Create GET /api/training-plans endpoint
    - List all plans for authenticated user
    - Include title, sport, goal, dates, status, adherence percentage
    - Calculate adherence as ratio of completed to total sessions
    - Load and render within 2 seconds at p95
    - _Requirements: 12.1, 12.2, 12.3, 12.5, 18.1, 20.2_

  - [x] 12.2 Create GET /api/training-plans/{plan_id} endpoint
    - Return detailed plan with all weeks and sessions
    - Include header, progress bar data, weekly timeline, session grid
    - Include matched activity details for completed sessions
    - Load and render within 2 seconds at p95
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.6, 18.2, 20.2_

  - [x] 12.3 Create GET /api/training-plans/{plan_id}/adherence endpoint
    - Return adherence time series for charting
    - Include weekly adherence and overall adherence
    - _Requirements: 13.5_

- [x] 13. Implement Plan Progress Screen UI
  - [x] 13.1 Create Plans List View component
    - Fetch plans from /api/training-plans
    - Render card grid with plan details
    - Display progress bars showing adherence percentage
    - Display status badges (draft, active, completed, abandoned)
    - Navigate to Plan Detail View on card click
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [x] 13.2 Create Plan Detail View component
    - Fetch plan details from /api/training-plans/{plan_id}
    - Render header with title, sport, goal, date range
    - Render overall progress bar
    - Render weekly timeline showing all weeks
    - Render session grid in calendar view with completion status
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 13.3 Create adherence chart component
    - Fetch adherence data from /api/training-plans/{plan_id}/adherence
    - Render line chart showing weekly adherence percentages
    - Display overall adherence metric
    - _Requirements: 13.5_

- [x] 14. Integrate Strava sync with session matching
  - [x] 14.1 Create Strava webhook handler
    - Receive new activity notifications from Strava API
    - Store activity in database
    - Trigger SessionMatcher for new activities
    - _Requirements: 14.1_

  - [x] 14.2 Wire session matching to Strava sync
    - Call SessionMatcher.match_activity for each new activity
    - Update training_plan_sessions table on successful match
    - Log matching results for monitoring
    - _Requirements: 14.1, 14.3, 14.4, 14.5_

- [x] 15. Checkpoint - Verify end-to-end flow
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Implement security and performance monitoring
  - [x] 16.1 Add user_id validation to all data access
    - Verify RAG_Engine includes user_id filters in vector queries
    - Verify Training_Plan_Engine includes user_id filters in database queries
    - Verify Chat_System includes user_id filters in tool invocations
    - Verify Plan_Progress_Screen includes user_id filters in API calls
    - Log security violations when queries attempt cross-user access
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_

  - [x] 16.2 Add performance monitoring and logging
    - Log chat response latency (target: p95 < 3 seconds)
    - Log vector retrieval latency (target: p95 < 500ms)
    - Log plan screen load times (target: p95 < 2 seconds)
    - Log when performance thresholds are exceeded
    - _Requirements: 17.1, 17.2, 17.3, 18.1, 18.2, 18.3_

- [x] 17. Final integration and wiring
  - [x] 17.1 Wire RAG Engine to Chat Service
    - Integrate context retrieval into chat message handler
    - Integrate session persistence on session end
    - Test context retrieval with active buffer and vector store
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 17.2 Wire Training Plan Engine to Chat Tools
    - Integrate plan generation into save_training_plan tool
    - Integrate plan retrieval into get_training_plan tool
    - Test plan generation flow with confirmation
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3, 9.4_

  - [x] 17.3 Wire Session Matcher to Strava Sync
    - Integrate automatic matching on activity import
    - Test matching with various activity types and times
    - Verify adherence updates after matching
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 15.4_

  - [x] 17.4 Wire Plan Progress Screen to backend APIs
    - Connect Plans List View to /api/training-plans
    - Connect Plan Detail View to /api/training-plans/{plan_id}
    - Connect adherence chart to /api/training-plans/{plan_id}/adherence
    - Test UI updates after Strava sync
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

- [x] 18. Final checkpoint - Complete system verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks reference specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Implementation follows bottom-up approach: data layer → service layer → API layer → UI layer
- User-scoped security is enforced at every data access point
- Performance targets are validated through monitoring and logging
- The design uses Python (FastAPI, SQLAlchemy) matching the existing codebase
