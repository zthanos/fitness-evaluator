# Requirements Document

## Introduction

This document specifies requirements for upgrading the Fitness Platform with three interconnected features: Context-Engineered Chat (replacing blind history with RAG-based retrieval), Training Plan Engine (AI-generated, activity-aware plans), and Plan Progress Screen (visual tracking with automatic Strava sync). The upgrade enhances chat intelligence through dynamic context retrieval, enables personalized training plan generation and storage, and provides athletes with visual progress tracking automatically updated from synchronized activities.

## Glossary

- **Chat_System**: The conversational AI interface that responds to athlete queries
- **Active_Session_Buffer**: In-memory storage of messages from the current chat session
- **Vector_Store**: Database component that stores and retrieves semantically similar chat history using embeddings
- **RAG_Engine**: Retrieval-Augmented Generation system that retrieves relevant context before generating responses
- **Training_Plan_Engine**: AI component that generates personalized training plans based on athlete data
- **Plan_Progress_Screen**: User interface displaying training plan details and adherence metrics
- **Strava_Sync**: Background process that imports athlete activities from Strava API
- **Session_Matcher**: Component that matches imported Strava activities to planned training sessions
- **Adherence_Score**: Percentage metric indicating how closely an athlete followed their training plan
- **Chat_Session**: A conversation instance with unique identifier and timestamp
- **Training_Plan**: Structured multi-week training program with scheduled sessions
- **Training_Session**: Individual workout within a training plan with prescribed parameters
- **Athlete_Goal**: User-defined fitness objective linked to training plans
- **Tool**: Function the Chat_System can invoke to retrieve data or perform actions

## Requirements

### Requirement 1: Context-Engineered Chat Retrieval

**User Story:** As an athlete, I want the chat to remember relevant past conversations, so that I don't have to repeat context in every session

#### Acceptance Criteria

1. WHEN an athlete sends a message, THE Chat_System SHALL retrieve messages from the Active_Session_Buffer
2. WHEN an athlete sends a message, THE RAG_Engine SHALL retrieve semantically similar messages from the Vector_Store within 500ms
3. THE RAG_Engine SHALL rank retrieved messages using weighted scoring: recency weight + evaluation score weight + semantic similarity weight
4. THE Chat_System SHALL combine Active_Session_Buffer messages and Vector_Store results before generating a response
5. WHEN a chat session ends, THE Chat_System SHALL persist all session messages to the Vector_Store with key format chat:{user_id}:{session_id}:{date}:eval_{score}
6. THE Vector_Store SHALL index chat messages using semantic embeddings for similarity search
7. FOR ALL vector queries, THE RAG_Engine SHALL scope results to the requesting athlete's user_id only

### Requirement 2: Chat Session Management

**User Story:** As an athlete, I want to delete old chat sessions, so that I can remove outdated or irrelevant conversations

#### Acceptance Criteria

1. WHEN an athlete requests session deletion, THE Chat_System SHALL remove the session from persistent storage
2. WHEN a session is deleted, THE Chat_System SHALL remove all associated vectors from the Vector_Store using prefix match on key pattern chat:{user_id}:{session_id}:*
3. THE Chat_System SHALL complete session deletion within 2 seconds
4. WHEN deletion fails, THE Chat_System SHALL log the error and return an error message to the athlete

### Requirement 3: Multi-Step Tool Use

**User Story:** As an athlete, I want the chat to gather information before answering, so that responses are based on my actual data

#### Acceptance Criteria

1. WHEN the Chat_System determines multiple tools are needed, THE Chat_System SHALL execute tools sequentially before generating a final response
2. THE Chat_System SHALL pass results from earlier tool calls to subsequent tool calls in the same reasoning chain
3. WHEN all required tools have executed, THE Chat_System SHALL generate a final response incorporating all tool results
4. THE Chat_System SHALL complete multi-step tool execution and response generation within 3 seconds at p95

### Requirement 4: Clarification Requests

**User Story:** As an athlete, I want the chat to ask for clarification when my request is unclear, so that I receive accurate responses

#### Acceptance Criteria

1. WHEN the Chat_System cannot determine user intent with confidence, THE Chat_System SHALL generate a clarification question
2. THE Chat_System SHALL include specific options or examples in clarification questions
3. WHEN the athlete provides clarification, THE Chat_System SHALL process the original request with the additional context

### Requirement 5: Web Search Integration

**User Story:** As an athlete, I want the chat to search for current fitness information, so that I receive up-to-date domain knowledge

#### Acceptance Criteria

1. WHEN the Chat_System determines external information is needed, THE Chat_System SHALL invoke the search_web tool
2. THE Chat_System SHALL include search results in the context for response generation
3. THE Chat_System SHALL cite sources when using information from web search results
4. THE Chat_System SHALL complete web search and response generation within 3 seconds at p95

### Requirement 6: Chat Tool Availability

**User Story:** As an athlete, I want the chat to access my fitness data and goals, so that responses are personalized to my situation

#### Acceptance Criteria

1. THE Chat_System SHALL provide the save_athlete_goal tool for storing athlete objectives
2. THE Chat_System SHALL provide the get_my_goals tool for retrieving stored athlete objectives
3. THE Chat_System SHALL provide the get_my_recent_activities tool for retrieving synchronized Strava activities
4. THE Chat_System SHALL provide the get_my_weekly_metrics tool for retrieving aggregated training metrics
5. THE Chat_System SHALL provide the save_training_plan tool for persisting generated training plans
6. THE Chat_System SHALL provide the get_training_plan tool for retrieving existing training plans
7. FOR ALL tool invocations, THE Chat_System SHALL scope data access to the requesting athlete's user_id only

### Requirement 7: Training Plan Data Schema

**User Story:** As a developer, I want training plans stored in a relational schema, so that plans can be queried and updated efficiently

#### Acceptance Criteria

1. THE Training_Plan_Engine SHALL store plans in a training_plans table with columns: id, user_id, title, sport, goal_id, start_date, end_date, status, created_at
2. THE Training_Plan_Engine SHALL store weekly structures in a training_plan_weeks table with columns: id, plan_id, week_number, focus, volume_target
3. THE Training_Plan_Engine SHALL store individual sessions in a training_plan_sessions table with columns: id, week_id, day_of_week, session_type, duration_minutes, intensity, description, completed, matched_activity_id
4. THE Training_Plan_Engine SHALL enforce referential integrity with foreign keys: training_plan_weeks.plan_id → training_plans.id, training_plan_sessions.week_id → training_plan_weeks.id
5. THE Training_Plan_Engine SHALL apply row-level security policies ensuring athletes can only access their own plans

### Requirement 8: Activity-Aware Plan Generation

**User Story:** As an athlete, I want training plans based on my recent activity history, so that plans match my current fitness level

#### Acceptance Criteria

1. WHEN generating a training plan, THE Training_Plan_Engine SHALL retrieve the athlete's recent activities using get_my_recent_activities
2. WHEN generating a training plan, THE Training_Plan_Engine SHALL retrieve the athlete's weekly metrics using get_my_weekly_metrics
3. THE Training_Plan_Engine SHALL incorporate retrieved activity data and metrics into plan generation prompts
4. THE Training_Plan_Engine SHALL generate plans with progressive volume increases based on current training load

### Requirement 9: Plan Generation Flow with Confirmation

**User Story:** As an athlete, I want to review a training plan before it's saved, so that I can request changes if needed

#### Acceptance Criteria

1. WHEN the Training_Plan_Engine generates a plan, THE Chat_System SHALL present the plan to the athlete for review
2. THE Chat_System SHALL wait for athlete confirmation before invoking save_training_plan
3. WHEN the athlete requests modifications, THE Training_Plan_Engine SHALL regenerate the plan incorporating the requested changes
4. WHEN the athlete confirms, THE Chat_System SHALL invoke save_training_plan and persist the plan to the database

### Requirement 10: Plan Iteration Support

**User Story:** As an athlete, I want to modify existing training plans, so that I can adapt plans as my situation changes

#### Acceptance Criteria

1. WHEN an athlete requests plan modifications, THE Chat_System SHALL retrieve the existing plan using get_training_plan
2. THE Chat_System SHALL present the current plan details to the athlete
3. THE Training_Plan_Engine SHALL generate an updated plan incorporating the requested modifications and existing plan structure
4. WHEN the athlete confirms changes, THE Chat_System SHALL update the existing plan record in-place and set updated_at to current timestamp
5. THE Training_Plan_Engine SHALL preserve the original plan id and created_at timestamp during updates

### Requirement 11: Plan-Goal Linking

**User Story:** As an athlete, I want training plans linked to my goals, so that I can track which plans support which objectives

#### Acceptance Criteria

1. WHEN generating a training plan, THE Training_Plan_Engine SHALL accept a goal_id parameter
2. THE Training_Plan_Engine SHALL store the goal_id in the training_plans table
3. WHEN retrieving a training plan, THE Chat_System SHALL include the associated goal information
4. WHERE a goal is deleted, THE Training_Plan_Engine SHALL set the goal_id to null for associated plans

### Requirement 12: Plans List View

**User Story:** As an athlete, I want to see all my training plans in a list, so that I can quickly access any plan

#### Acceptance Criteria

1. THE Plan_Progress_Screen SHALL display a list of all training plans for the authenticated athlete
2. FOR EACH plan in the list, THE Plan_Progress_Screen SHALL display title, sport, goal, start_date, end_date, status, and adherence percentage
3. THE Plan_Progress_Screen SHALL calculate adherence percentage as the ratio of completed sessions to total sessions
4. WHEN an athlete selects a plan card, THE Plan_Progress_Screen SHALL navigate to the Plan Detail View
5. THE Plan_Progress_Screen SHALL load and render the plans list within 2 seconds

### Requirement 13: Plan Detail View

**User Story:** As an athlete, I want to see detailed progress for a training plan, so that I can track my adherence and upcoming sessions

#### Acceptance Criteria

1. THE Plan_Progress_Screen SHALL display a header with plan title, sport, goal, and date range
2. THE Plan_Progress_Screen SHALL display an overall progress bar showing percentage of plan duration completed
3. THE Plan_Progress_Screen SHALL display a weekly timeline showing all weeks in the plan
4. THE Plan_Progress_Screen SHALL display a session grid showing all sessions with completion status
5. THE Plan_Progress_Screen SHALL display an adherence chart showing weekly adherence percentages
6. THE Plan_Progress_Screen SHALL display an "Ask Coach" button that opens the Chat screen with the plan context pre-loaded
7. THE Plan_Progress_Screen SHALL load and render the plan detail view within 2 seconds

### Requirement 14: Automatic Session Matching

**User Story:** As an athlete, I want my Strava activities automatically matched to planned sessions, so that progress updates without manual input

#### Acceptance Criteria

1. WHEN the Strava_Sync imports a new activity, THE Session_Matcher SHALL identify candidate training sessions within 24 hours of the activity timestamp
2. THE Session_Matcher SHALL compare activity sport type, duration, and intensity to candidate session parameters
3. WHEN a match confidence exceeds 80%, THE Session_Matcher SHALL update the training_plan_sessions.matched_activity_id and set completed to true
4. WHEN a match confidence is below 80%, THE Session_Matcher SHALL leave the session unmatched
5. THE Session_Matcher SHALL process each imported activity within 5 seconds

### Requirement 15: Adherence Score Calculation

**User Story:** As an athlete, I want to see adherence scores at multiple levels, so that I understand how well I'm following my plan

#### Acceptance Criteria

1. THE Plan_Progress_Screen SHALL calculate per-session adherence as 100% when completed is true, 0% otherwise
2. THE Plan_Progress_Screen SHALL calculate per-week adherence as the percentage of completed sessions in that week
3. THE Plan_Progress_Screen SHALL calculate overall plan adherence as the percentage of completed sessions across all weeks
4. THE Plan_Progress_Screen SHALL update adherence scores within 10 seconds after the Session_Matcher updates session completion status

### Requirement 16: Data Safety for Schema Changes

**User Story:** As a developer, I want schema migrations to be additive only, so that existing data is never lost or corrupted

#### Acceptance Criteria

1. THE Training_Plan_Engine SHALL create new tables using CREATE TABLE IF NOT EXISTS statements
2. THE Training_Plan_Engine SHALL add new columns using ALTER TABLE ADD COLUMN statements
3. THE Training_Plan_Engine SHALL reject any migration containing DROP, TRUNCATE, or UPDATE operations on existing data
4. THE Training_Plan_Engine SHALL validate all migrations before execution

### Requirement 17: Chat Response Performance

**User Story:** As an athlete, I want chat responses to be fast, so that conversations feel natural and responsive

#### Acceptance Criteria

1. THE Chat_System SHALL generate and return responses within 3 seconds at p95 latency
2. THE RAG_Engine SHALL complete vector retrieval within 500ms at p95 latency
3. WHEN performance thresholds are exceeded, THE Chat_System SHALL log performance metrics for monitoring

### Requirement 18: Plan Screen Performance

**User Story:** As an athlete, I want the plan progress screen to load quickly, so that I can check my progress without waiting

#### Acceptance Criteria

1. THE Plan_Progress_Screen SHALL load and render the plans list view within 2 seconds at p95 latency
2. THE Plan_Progress_Screen SHALL load and render the plan detail view within 2 seconds at p95 latency
3. WHEN performance thresholds are exceeded, THE Plan_Progress_Screen SHALL log performance metrics for monitoring

### Requirement 19: Parser for Training Plan Format

**User Story:** As a developer, I want to parse AI-generated training plans into structured data, so that plans can be stored in the database

#### Acceptance Criteria

1. WHEN the Training_Plan_Engine receives a generated plan, THE Plan_Parser SHALL parse the text into a structured Training_Plan object
2. WHEN the plan format is invalid, THE Plan_Parser SHALL return a descriptive error message
3. THE Plan_Pretty_Printer SHALL format Training_Plan objects back into human-readable text
4. FOR ALL valid Training_Plan objects, THE Plan_Parser SHALL satisfy the round-trip property: parse(print(plan)) produces an equivalent Training_Plan object

### Requirement 20: Security for User-Scoped Queries

**User Story:** As a platform administrator, I want all data access scoped to the requesting user, so that athletes cannot access other athletes' data

#### Acceptance Criteria

1. THE RAG_Engine SHALL include user_id filters in all vector store queries
2. THE Training_Plan_Engine SHALL include user_id filters in all database queries for training plans
3. THE Chat_System SHALL include user_id filters in all tool invocations
4. THE Plan_Progress_Screen SHALL include user_id filters in all data fetching operations
5. WHEN a query attempts to access data for a different user_id, THE system SHALL reject the query and log a security violation
