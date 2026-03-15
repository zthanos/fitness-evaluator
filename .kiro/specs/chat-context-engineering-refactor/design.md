Design Document: Chat Context Engineering Refactor
Overview
This design document specifies the technical architecture for migrating the chat system from its current ad-hoc implementation to the Context Engineering (CE) architecture. The refactor transforms chat from manual prompt building and direct LLM calls into a structured, layered system matching the evaluation system's approach.

Design Goals
Architectural Consistency: Achieve parity with evaluation system's CE architecture
Separation of Concerns: Decouple session management, context building, tool orchestration, and LLM invocation
Maintainability: Replace hardcoded prompts with versioned templates and configuration
Observability: Add comprehensive telemetry for debugging and performance monitoring
Reliability: Implement model fallback, error handling, and bounded execution
Backward Compatibility: Maintain existing API contracts and session data
System Context
The fitness coaching platform provides AI-powered coaching through chat conversations. The current implementation has several architectural issues:

Current Problems:

ChatMessageHandler is monolithic (session + context + tools + LLM invocation)
Manual prompt building with string concatenation
No versioned prompts or domain knowledge injection
Direct LLM client calls without fallback
No telemetry or performance monitoring
Full session history sent every turn (token waste)
No athlete behavior summary or personalization layer
Target State:

Clean separation: ChatSessionService, ChatAgent, ChatContextBuilder, ToolOrchestrator, LLMAdapter
Versioned Jinja2 prompt templates
Structured context layers with token budget enforcement
Intent-aware RAG retrieval with evidence cards
Model abstraction with automatic fallback
Comprehensive telemetry and observability
Architecture
Module Structure
The refactored chat system organizes components into clear responsibility boundaries:

app/
├── api/
│   └── chat.py                      # API endpoints (unchanged interface)
├── services/
│   ├── chat_session_service.py      # NEW: Session lifecycle management
│   ├── chat_agent.py                # NEW: Runtime execution owner
│   ├── chat_message_handler.py      # REFACTORED: Thin coordinator
│   └── tool_orchestrator.py         # NEW: Multi-step tool execution
├── ai/
│   ├── context/
│   │   └── chat_context.py          # ACTIVATED: ChatContextBuilder
│   ├── adapter/
│   │   └── langchain_adapter.py     # SHARED: LLMAdapter with fallback
│   ├── prompts/
│   │   ├── system/
│   │   │   └── coach_chat_v1.0.0.j2 # NEW: Versioned system prompt
│   │   └── tasks/
│   │       └── chat_response_v1.0.0.j2 # NEW: Task instructions
│   └── telemetry/
│       └── invocation_logger.py     # SHARED: Telemetry logging
Component Responsibility Map
ChatMessageHandler (Refactored)
Role: Thin coordinator between API and execution layer

Responsibilities:

Receive chat request from API endpoint
Delegate to ChatSessionService for session operations
Delegate to ChatAgent for execution
Return response to API
NOT Responsible For:

Session lifecycle management
Context building
Tool execution
LLM invocation
Prompt ownership
Interface:

class ChatMessageHandler:
    def __init__(self, db: Session, session_service: ChatSessionService, agent: ChatAgent):
        self.db = db
        self.session_service = session_service
        self.agent = agent
    
    async def handle_message(
        self,
        user_message: str,
        session_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Handle chat message by coordinating session and agent.
        
        Flow:
        1. Load session context via session_service
        2. Execute via agent
        3. Persist response via session_service
        4. Return response
        """
ChatSessionService (New)
Role: Session lifecycle and persistence management

Responsibilities:

Create/load/delete chat sessions
Maintain active in-memory message buffer
Load session messages from database
Append user/assistant messages to buffer
Persist session to database and vector store
Clear buffer on session switch
NOT Responsible For:

Context building logic
Message content generation
Tool execution
LLM invocation
Interface:

class ChatSessionService:
    def __init__(self, db: Session, rag_engine: RAGEngine):
        self.db = db
        self.rag_engine = rag_engine
        self.active_buffers: Dict[int, List[ChatMessage]] = {}
    
    def create_session(self, athlete_id: int, title: str) -> int:
        """Create new session and return session_id"""
    
    def load_session(self, session_id: int) -> List[ChatMessage]:
        """Load session messages into active buffer"""
    
    def append_messages(self, session_id: int, user_msg: str, assistant_msg: str):
        """Append messages to active buffer"""
    
    def get_active_buffer(self, session_id: int) -> List[ChatMessage]:
        """Get current active buffer for session"""
    
    def persist_session(self, session_id: int, eval_score: Optional[float] = None):
        """Persist session to database and vector store"""
    
    def clear_buffer(self, session_id: int):
        """Clear active buffer for session"""
ChatAgent (New)
Role: Runtime execution owner for chat flow

Responsibilities:

Request context from ChatContextBuilder
Invoke ToolOrchestrator for tool execution
Invoke LLMAdapter for model calls
Return final response with metadata
Coordinate multi-step execution flow
NOT Responsible For:

Session persistence
Context layer assembly
Individual tool execution
Direct model invocation
Interface:

class ChatAgent:
    def __init__(
        self,
        context_builder: ChatContextBuilder,
        tool_orchestrator: ToolOrchestrator,
        llm_adapter: LLMAdapter
    ):
        self.context_builder = context_builder
        self.tool_orchestrator = tool_orchestrator
        self.llm_adapter = llm_adapter
    
    async def execute(
        self,
        user_message: str,
        session_id: int,
        user_id: int,
        conversation_history: List[ChatMessage]
    ) -> Dict[str, Any]:
        """
        Execute chat request with full CE pipeline.
        
        Flow:
        1. Build context via ChatContextBuilder
        2. Invoke LLM via LLMAdapter
        3. If tool calls needed, delegate to ToolOrchestrator
        4. Return final response with metadata
        
        Returns:
            {
                'content': str,
                'tool_calls_made': int,
                'iterations': int,
                'latency_ms': float,
                'model_used': str,
                'context_token_count': int,
                'response_token_count': int
            }
        """
ChatContextBuilder (Activated)
Role: Structured context assembly with CE layers

Responsibilities:

Load versioned system and task prompts
Inject athlete behavior summary
Perform intent-aware RAG retrieval
Select relevant conversation history dynamically
Assemble layered context with token budget enforcement
Generate evidence cards for retrieved data
NOT Responsible For:

Session management
Tool execution
LLM invocation
Response generation
Interface (already exists in 
chat_context.py
):

class ChatContextBuilder(ContextBuilder):
    def __init__(self, db: Session, token_budget: int = 2400):
        super().__init__(token_budget)
        self.db = db
        self.intent_router = IntentRouter()
        self.rag_retriever = RAGRetriever(db)
    
    def gather_data(
        self,
        query: str,
        athlete_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> 'ChatContextBuilder':
        """
        Gather data for chat response using intent-aware retrieval.
        
        Steps:
        1. Classify query intent
        2. Retrieve relevant data with intent-specific policy
        3. Select relevant conversation history
        4. Generate athlete behavior summary
        5. Add all layers to context
        """
ToolOrchestrator (New)
Role: Multi-step tool execution with ReAct pattern

Responsibilities:

Execute zero, one, or many tool calls
Support sequential tool chains
Pass tool results to subsequent calls
Enforce iteration limits (max 5)
Handle tool failures gracefully
Log tool invocations for debugging
NOT Responsible For:

Context building
LLM invocation
Session management
Individual tool implementation
Interface:

class ToolOrchestrator:
    def __init__(
        self,
        llm_adapter: LLMAdapter,
        tool_registry: Dict[str, Callable],
        max_iterations: int = 5
    ):
        self.llm_adapter = llm_adapter
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations
    
    async def orchestrate(
        self,
        conversation: List[Dict[str, str]],
        tool_definitions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute multi-step tool orchestration with ReAct pattern.
        
        Flow:
        1. Invoke LLM with tool definitions
        2. If tool calls requested, execute sequentially
        3. Append tool results to conversation
        4. Repeat until no more tool calls or max iterations
        5. Return final response
        
        Returns:
            {
                'content': str,
                'tool_calls_made': int,
                'iterations': int,
                'tool_results': List[Dict]
            }
        """
LLMAdapter (Shared)
Role: Model invocation abstraction with fallback

Responsibilities:

Abstract model provider details (Ollama, LM Studio, OpenAI)
Implement automatic fallback (Mixtral → Llama)
Count tokens for input and output
Emit telemetry for all invocations
Support streaming responses
Handle connection errors and timeouts
NOT Responsible For:

Context building
Tool execution
Session management
Prompt template loading
Interface (already exists in 
langchain_adapter.py
):

class LangChainAdapter(LLMProviderAdapter):
    def __init__(
        self,
        primary_model: str = "mixtral:8x7b-instruct",
        fallback_model: str = "llama3.1:8b-instruct",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        invocation_logger: Optional[InvocationLogger] = None
    ):
        """Initialize adapter with primary and fallback models"""
    
    def invoke(
        self,
        context: Context,
        contract: Type[BaseModel],
        operation_type: str = "chat_response",
        athlete_id: Optional[int] = None
    ) -> LLMResponse:
        """
        Invoke LLM with automatic fallback and telemetry.
        
        Flow:
        1. Try primary model
        2. On timeout/connection error, retry with fallback
        3. Log telemetry
        4. Return response with metadata
        """
Data Flow Diagrams
Current Chat Flow (Legacy)
sequenceDiagram
    participant API as POST /chat
    participant Handler as ChatMessageHandler
    participant RAG as RAGEngine
    participant LLM as LLMClient
    participant DB as Database
    
    API->>Handler: user_message, session_id
    Handler->>DB: Load session messages
    Handler->>RAG: retrieve_context(query)
    RAG-->>Handler: context string
    Handler->>Handler: _build_conversation (manual)
    Handler->>LLM: chat_completion (direct call)
    
    alt Tool calls needed
        LLM-->>Handler: response with tool_calls
        Handler->>Handler: _orchestrate_tools (loop)
        Handler->>LLM: chat_completion (with results)
    end
    
    LLM-->>Handler: final response
    Handler->>DB: Save messages
    Handler-->>API: response
Problems:

Handler does everything (monolithic)
Manual prompt building
Direct LLM calls (no fallback)
Full session history sent
No telemetry
No athlete behavior summary
Target Chat Flow (CE Architecture)
sequenceDiagram
    participant API as POST /chat
    participant Handler as ChatMessageHandler
    participant Session as ChatSessionService
    participant Agent as ChatAgent
    participant Context as ChatContextBuilder
    participant Tools as ToolOrchestrator
    participant Adapter as LLMAdapter
    participant DB as Database
    
    API->>Handler: user_message, session_id
    Handler->>Session: load_session(session_id)
    Session->>DB: Query messages
    Session-->>Handler: conversation_history
    
    Handler->>Agent: execute(message, history)
    Agent->>Context: gather_data(query, athlete_id, history)
    Context->>Context: Classify intent
    Context->>Context: Retrieve with policy
    Context->>Context: Select relevant history
    Context->>Context: Generate athlete summary
    Context-->>Agent: Context (validated, token-budgeted)
    
    Agent->>Adapter: invoke(context, ChatResponseContract)
    Adapter->>Adapter: Try primary model
    
    alt Tool calls needed
        Adapter-->>Agent: response with tool_calls
        Agent->>Tools: orchestrate(conversation, tools)
        Tools->>Tools: Execute tools sequentially
        Tools->>Adapter: invoke with tool results
    end
    
    Adapter-->>Agent: final response + metadata
    Agent-->>Handler: response + metadata
    
    Handler->>Session: append_messages(user, assistant)
    Session->>DB: Save messages
    Session->>DB: Persist to vector store
    Handler-->>API: response
Benefits:

Clean separation of concerns
Versioned prompts
Intent-aware retrieval
Dynamic history selection
Athlete behavior summary
Model fallback
Comprehensive telemetry
Token budget enforcement
Runtime Context Model
The CE architecture builds context in structured layers:

@dataclass
class Context:
    """Structured context for chat operations"""
    
    # Layer 1: System Instructions (Persona + Behavioral Rules)
    system_instructions: str  # From app/ai/prompts/system/coach_chat_v1.0.0.j2
    
    # Layer 2: Task Instructions (Operation-specific objectives)
    task_instructions: str  # From app/ai/prompts/tasks/chat_response_v1.0.0.j2
    
    # Layer 3: Domain Knowledge (Sport science reference data)
    domain_knowledge: Dict[str, Any]  # From app/ai/config/domain_knowledge.yaml
    
    # Layer 4: Athlete Behavior Summary (Condensed profile)
    athlete_behavior_summary: str  # Generated from recent patterns
    
    # Layer 5: Structured Athlete State (Current goals, plan, metrics)
    structured_athlete_state: Dict[str, Any]  # Active goals, current plan
    
    # Layer 6: Retrieved Evidence (Intent-aware RAG results)
    retrieved_evidence: List[EvidenceCard]  # With source IDs
    
    # Layer 7: Dynamic History (Relevant conversation turns)
    dynamic_history: List[Dict[str, str]]  # Selected, not full session
    
    # Layer 8: Current User Message
    current_user_message: str
    
    # Metadata
    token_count: int
    intent: Intent
Layer Details:

System Instructions (200-300 tokens)

AI coach persona
Behavioral constraints
Communication style
Tool usage guidelines
Task Instructions (100-150 tokens)

Respond to athlete query
Use tools to gather data
Provide evidence-based advice
Reference specific data points
Domain Knowledge (150-200 tokens)

Training zones (Z1-Z5)
Effort levels (easy/moderate/hard/max)
Recovery guidelines
Nutrition targets
Athlete Behavior Summary (150-200 tokens)

Training patterns (e.g., "runs 4x/week, prefers morning")
Preferences (e.g., "dislikes high-intensity intervals")
Recent trends (e.g., "increasing volume steadily")
Past feedback (e.g., "responds well to structured plans")
Structured Athlete State (100-150 tokens)

Active goals with targets and dates
Current training plan (if any)
Recent metrics (weight, RHR, sleep)
Retrieved Evidence (400-600 tokens)

Intent-specific data (recent activities, trends, etc.)
Formatted as evidence cards with source IDs
Limited to top 5-10 most relevant records
Dynamic History (600-800 tokens)

Last 3-5 relevant turns
Contextually important past turns
NOT full session history
Current User Message (50-200 tokens)

The athlete's current question/request
Total Budget: 2400 tokens (enforced by ContextBuilder)

Sequence Diagrams by Phase
Phase 1: Extract ChatSessionService
sequenceDiagram
    participant API
    participant Handler as ChatMessageHandler
    participant Session as ChatSessionService (NEW)
    participant DB
    
    API->>Handler: handle_message(message, session_id)
    Handler->>Session: load_session(session_id)
    Session->>DB: Query messages
    Session-->>Handler: conversation_history
    
    Note over Handler: Execute chat logic (unchanged for now)
    
    Handler->>Session: append_messages(user_msg, assistant_msg)
    Session->>DB: Save messages
    Handler-->>API: response
Changes:

Session operations extracted to ChatSessionService
Handler delegates session management
Active buffer owned by ChatSessionService
Phase 2: Move Context Composition to CE Path
sequenceDiagram
    participant Handler as ChatMessageHandler
    participant Session as ChatSessionService
    participant Context as ChatContextBuilder (ACTIVATED)
    participant Intent as IntentRouter
    participant RAG as RAGRetriever
    
    Handler->>Session: get_active_buffer(session_id)
    Session-->>Handler: conversation_history
    
    Handler->>Context: gather_data(query, athlete_id, history)
    Context->>Intent: classify(query)
    Intent-->>Context: intent (e.g., recent_performance)
    
    Context->>RAG: retrieve(query, athlete_id, intent)
    RAG-->>Context: retrieved_data + evidence_cards
    
    Context->>Context: select_relevant_history(history, query)
    Context->>Context: generate_athlete_summary(athlete_id)
    Context->>Context: load_prompts(system, task)
    Context->>Context: build() # Validate token budget
    Context-->>Handler: Context (validated)
    
    Note over Handler: Use context for LLM invocation
Changes:

ChatContextBuilder activated
Intent-aware retrieval
Dynamic history selection
Athlete behavior summary
Token budget enforcement
Manual prompt building removed
Phase 3: Introduce ChatAgent
sequenceDiagram
    participant Handler as ChatMessageHandler (THIN)
    participant Session as ChatSessionService
    participant Agent as ChatAgent (NEW)
    participant Context as ChatContextBuilder
    participant LLM as LLMAdapter
    
    Handler->>Session: load_session(session_id)
    Session-->>Handler: conversation_history
    
    Handler->>Agent: execute(message, session_id, user_id, history)
    Agent->>Context: gather_data(...)
    Context-->>Agent: context
    
    Agent->>LLM: invoke(context, ChatResponseContract)
    LLM-->>Agent: response + metadata
    
    Agent-->>Handler: response + metadata
    Handler->>Session: append_messages(...)
    Handler-->>API: response
Changes:

ChatAgent owns execution flow
Handler becomes thin coordinator
Clean orchestration boundaries
Phase 4: Extract ToolOrchestrator
sequenceDiagram
    participant Agent as ChatAgent
    participant Tools as ToolOrchestrator (NEW)
    participant LLM as LLMAdapter
    
    Agent->>LLM: invoke(context, contract)
    LLM-->>Agent: response with tool_calls
    
    Agent->>Tools: orchestrate(conversation, tool_defs)
    
    loop Max 5 iterations
        Tools->>LLM: invoke with tool definitions
        LLM-->>Tools: response
        
        alt Tool calls present
            Tools->>Tools: execute_tools_sequentially()
            Tools->>Tools: append_tool_results()
        else No tool calls
            Tools-->>Agent: final response
        end
    end
    
    Tools-->>Agent: response + metadata
Changes:

ToolOrchestrator handles multi-step execution
ReAct pattern implementation
Bounded iteration
Tool failure handling
Phase 5: Switch Chat to Shared LLMAdapter
sequenceDiagram
    participant Agent as ChatAgent
    participant Adapter as LLMAdapter (SHARED)
    participant Telemetry as InvocationLogger
    participant Primary as Mixtral
    participant Fallback as Llama
    
    Agent->>Adapter: invoke(context, contract)
    
    Adapter->>Primary: Try primary model
    
    alt Primary succeeds
        Primary-->>Adapter: response
    else Primary fails (timeout/connection)
        Adapter->>Fallback: Retry with fallback
        Fallback-->>Adapter: response
    end
    
    Adapter->>Telemetry: log(tokens, latency, model_used)
    Adapter-->>Agent: response + metadata
Changes:

Shared LLMAdapter for chat and evaluation
Automatic fallback
Comprehensive telemetry
Token counting
Migration Strategy
Feature Flag Implementation
# app/config.py
class Settings(BaseSettings):
    USE_CE_CHAT_RUNTIME: bool = False  # Feature flag
    
    # Legacy settings
    LEGACY_CHAT_ENABLED: bool = True
    
    # CE settings
    CE_CHAT_TOKEN_BUDGET: int = 2400
    CE_CHAT_MAX_TOOL_ITERATIONS: int = 5
Runtime Selection
# app/services/chat_message_handler.py
class ChatMessageHandler:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        
        if settings.USE_CE_CHAT_RUNTIME:
            # Initialize CE components
            self.session_service = ChatSessionService(db)
            self.agent = ChatAgent(...)
            self.runtime = "ce"
        else:
            # Use legacy path
            self.rag_engine = RAGEngine(db)
            self.llm_client = LLMClient()
            self.runtime = "legacy"
    
    async def handle_message(self, user_message: str, session_id: int):
        if self.runtime == "ce":
            return await self._handle_ce(user_message, session_id)
        else:
            return await self._handle_legacy(user_message, session_id)
Backward Compatibility
Database Schema:

No breaking changes to ChatSession or ChatMessage tables
Existing sessions load into new runtime
Vector store embeddings remain compatible
API Contracts:

Request/response formats unchanged
Streaming endpoints maintain SSE format
Error responses consistent
Session Migration:

# Existing sessions work with new runtime
def load_legacy_session(session_id: int) -> List[ChatMessage]:
    """Load legacy session into CE runtime"""
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).all()
    
    # Convert to CE format (no changes needed, same models)
    return messages
Component Interfaces
ChatSessionService Interface
class ChatSessionService:
    """Session lifecycle and persistence management"""
    
    def create_session(
        self,
        athlete_id: int,
        title: str = "New Chat"
    ) -> int:
        """
        Create new chat session.
        
        Returns:
            session_id: ID of created session
        """
    
    def load_session(
        self,
        session_id: int
    ) -> List[ChatMessage]:
        """
        Load session messages into active buffer.
        
        Returns:
            List of ChatMessage objects ordered chronologically
        """
    
    def get_active_buffer(
        self,
        session_id: int
    ) -> List[ChatMessage]:
        """
        Get current active buffer for session.
        
        Returns:
            List of ChatMessage objects in memory
        """
    
    def append_messages(
        self,
        session_id: int,
        user_message: str,
        assistant_message: str
    ) -> None:
        """
        Append user and assistant messages to active buffer.
        
        Does NOT persist to database yet.
        """
    
    def persist_session(
        self,
        session_id: int,
        eval_score: Optional[float] = None
    ) -> None:
        """
        Persist session to database and vector store.
        
        Args:
            session_id: Session to persist
            eval_score: Optional quality score for the session
        """
    
    def clear_buffer(
        self,
        session_id: int
    ) -> None:
        """Clear active buffer for session"""
    
    def delete_session(
        self,
        session_id: int
    ) -> None:
        """
        Delete session from database and vector store.
        
        Removes all messages and embeddings.
        """
ChatAgent Interface
class ChatAgent:
    """Runtime execution owner for chat flow"""
    
    async def execute(
        self,
        user_message: str,
        session_id: int,
        user_id: int,
        conversation_history: List[ChatMessage]
    ) -> Dict[str, Any]:
        """
        Execute chat request with full CE pipeline.
        
        Args:
            user_message: Current user query
            session_id: Session identifier
            user_id: Athlete identifier
            conversation_history: Previous messages from session
        
        Returns:
            {
                'content': str,              # Final response text
                'tool_calls_made': int,      # Number of tools executed
                'iterations': int,           # Tool orchestration iterations
                'latency_ms': float,         # Total execution time
                'model_used': str,           # Model name (primary or fallback)
                'context_token_count': int,  # Input tokens
                'response_token_count': int, # Output tokens
                'intent': str,               # Classified intent
                'evidence_cards': List[Dict] # Retrieved evidence
            }
        """
ToolOrchestrator Interface
class ToolOrchestrator:
    """Multi-step tool execution with ReAct pattern"""
    
    async def orchestrate(
        self,
        conversation: List[Dict[str, str]],
        tool_definitions: List[Dict[str, Any]],
        user_id: int
    ) -> Dict[str, Any]:
        """
        Execute multi-step tool orchestration.
        
        Args:
            conversation: Current conversation messages
            tool_definitions: Available tool schemas
            user_id: User ID for tool scoping
        
        Returns:
            {
                'content': str,           # Final response
                'tool_calls_made': int,   # Number of tools executed
                'iterations': int,        # Loop iterations
                'tool_results': List[Dict], # Results from each tool
                'max_iterations_reached': bool # Whether limit hit
            }
        """
Configuration Files
System Prompt Template
File: 
coach_chat_v1.0.0.j2

{# System Instructions for Chat v1.0.0 #}
{# Persona Definition #}
You are an expert fitness coach and training advisor with deep knowledge of:
- Exercise physiology and training principles
- Sports nutrition and body composition
- Performance optimization and race strategy
- Recovery, injury prevention, and periodization

{# Behavioral Constraints #}
You MUST:
- Base all advice on the athlete's actual data (activities, metrics, goals)
- Reference specific data points when making recommendations
- Use tools to gather information before providing advice
- Ask clarifying questions when intent is unclear
- Acknowledge data gaps explicitly

You MUST NOT:
- Provide medical advice or diagnose conditions
- Make assumptions about the athlete's health status
- Recommend supplements without proper context
- Ignore the athlete's stated goals or preferences

{# Communication Style #}
- Be friendly, supportive, and encouraging
- Use emojis occasionally for warmth (🏃, 💪, 🎯)
- Break down complex topics into digestible points
- Provide specific, actionable recommendations
- Celebrate progress and milestones

{# Tool Usage Guidelines #}
When the athlete asks about:
- Recent training → use get_my_recent_activities
- Goals → use get_my_goals
- Weekly metrics → use get_my_weekly_metrics
- Current fitness info → use search_web
- Saving goals → use save_athlete_goal
- Training plans → use save_training_plan or get_training_plan

Always gather data before making recommendations.
Present training plans for review before saving.
Task Prompt Template
File: 
chat_response_v1.0.0.j2

{# Task: Chat Response v1.0.0 #}
{# Objective #}
Respond to the athlete's query with personalized, evidence-based coaching advice.

{# Input Description #}
You have access to:
- Athlete Behavior Summary: Training patterns, preferences, recent trends
- Structured Athlete State: Active goals, current plan, recent metrics
- Retrieved Evidence: Relevant activities, metrics, logs, evaluations
- Dynamic History: Recent relevant conversation turns
- Current User Message: The athlete's current question

{# Analytical Focus #}
1. Understand the athlete's intent and needs
2. Reference specific data points from retrieved evidence
3. Provide actionable, personalized recommendations
4. Use tools to gather additional data if needed
5. Maintain conversation continuity

{# Output Guidelines #}
- Be concise but thorough
- Reference specific activities, metrics, or dates
- Provide 2-3 specific recommendations
- Explain the reasoning behind advice
- Encourage and motivate

{# Runtime Parameters #}
- Athlete ID: {{ athlete_id }}
- Session ID: {{ session_id }}
- Intent: {{ intent }}
- Timestamp: {{ timestamp }}
Performance Targets
Metric	Target	Measurement
Context Building	< 500ms	Time from request to context ready
RAG Retrieval	< 200ms	Time to retrieve 20 records
Simple Query (no tools)	< 3s p95	End-to-end latency
Multi-tool Query	< 5s p95	End-to-end latency with 2-3 tools
Token Budget	2400 tokens	Maximum context size
History Selection	3-5 turns	Relevant turns included
Evidence Cards	5-10 records	Retrieved data per query
Tool Iterations	Max 5	Bounded execution
Testing Strategy
Unit Tests
ChatSessionService:

test_create_session: Verify session creation
test_load_session: Verify message loading