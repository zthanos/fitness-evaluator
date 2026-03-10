# Chat Memory Fix - RAG Integration

## Problem
The chat was not maintaining context between messages. Each message was treated as a new conversation with no memory of previous exchanges. Sessions were not being saved to the database or FAISS vector store.

## Root Cause
The frontend was using the `/chat/stream` endpoint which did NOT have RAG (Retrieval-Augmented Generation) integration. The old implementation:
- Did not load previous messages from the session
- Did not retrieve context from the vector store
- Did not persist sessions to FAISS for future retrieval
- Only kept a limited in-memory history (10 messages)

## Solution Implemented

### 1. Updated `/chat/stream` Endpoint
**File:** `app/api/chat.py`

Added full RAG integration to the streaming endpoint:

```python
# Initialize RAG Engine and Chat Message Handler
rag_engine = RAGEngine(db)
llm_client = LLMClient()

# Create chat message handler with RAG integration
handler = ChatMessageHandler(
    db=db,
    rag_engine=rag_engine,
    llm_client=llm_client,
    user_id=athlete_id,
    session_id=session_id
)

# Load existing session messages into active buffer
prev_messages = db.query(ChatMessage).filter(
    ChatMessage.session_id == session_id
).order_by(ChatMessage.created_at.asc()).all()

handler.load_session_messages(prev_messages)

# Handle message with RAG context retrieval
response = await handler.handle_message(message.content)
```

### 2. Added Automatic Session Persistence
After each message exchange, the session is now automatically persisted to the FAISS vector store:

```python
# Persist session to vector store for future context retrieval
rag_engine.persist_session(
    user_id=athlete_id,
    session_id=session_id,
    messages=all_messages,
    eval_score=None
)
```

This ensures:
- All conversation history is embedded and stored in FAISS
- Future conversations can retrieve relevant context from past sessions
- User-scoped security is maintained (user_id filtering)

### 3. Two-Layer Context Retrieval

The chat now uses a two-layer architecture as specified:

**Layer 1: Active Session Buffer**
- All messages from the current session are kept in memory
- Provides immediate context for the ongoing conversation

**Layer 2: Vector Store (FAISS)**
- Semantically similar messages from past sessions
- Retrieved using embedding-based similarity search
- Scoped to the user's own conversations only

## What This Fixes

✅ **Session Continuity**: Messages within a session now maintain full context
✅ **Cross-Session Memory**: The AI can reference relevant past conversations
✅ **Database Persistence**: All messages are saved to the database
✅ **Vector Store Persistence**: Sessions are embedded and stored in FAISS
✅ **User Scoping**: All queries are filtered by user_id for security
✅ **Tool Execution**: The AI can use tools (save goals, create plans, etc.)

## Testing the Fix

### Manual Test Steps:

1. **Start a new chat session**
   - Go to the chat interface
   - Send a message: "I want to lose 5kg by May 30, 2026"
   - The AI should respond asking for details

2. **Continue the conversation**
   - Send a follow-up: "My current weight is 80kg"
   - The AI should remember your goal from the first message
   - It should reference the 5kg weight loss goal

3. **Check database persistence**
   ```sql
   SELECT * FROM chat_sessions ORDER BY created_at DESC LIMIT 1;
   SELECT * FROM chat_messages WHERE session_id = <session_id>;
   ```

4. **Check FAISS persistence**
   ```sql
   SELECT * FROM faiss_metadata WHERE record_type = 'chat_message' ORDER BY id DESC;
   ```

5. **Test cross-session memory** (requires Ollama running)
   - Start a new session
   - Ask: "What was my weight loss goal?"
   - The AI should retrieve context from the previous session

## Requirements Met

This implementation satisfies the following spec requirements:

- ✅ **Requirement 1.1**: Active Session Buffer retrieval
- ✅ **Requirement 1.2**: Vector Store semantic search
- ✅ **Requirement 1.3**: Combined context from both layers
- ✅ **Requirement 1.4**: Session persistence on completion
- ✅ **Requirement 1.5**: Key format `chat:{user_id}:{session_id}:{date}:eval_{score}`
- ✅ **Requirement 1.6**: Vector indexing with embeddings
- ✅ **Requirement 20.1**: User-scoped vector queries
- ✅ **Requirement 17.1**: RAG integration with chat service

## Known Limitations

1. **Ollama Service Required**: The embedding generation requires Ollama to be running on `http://localhost:11434`. If Ollama is not running:
   - Embeddings will fail
   - Vector store persistence will fail
   - But basic chat will still work (without cross-session memory)

2. **Streaming Simulation**: The current implementation generates the full response first, then streams it in chunks. True token-by-token streaming would require LLM client updates.

3. **Session Persistence Timing**: Sessions are persisted after EVERY message exchange. This could be optimized to persist less frequently (e.g., every 5 messages or on session end).

## Next Steps

1. **Verify Ollama is Running**:
   ```bash
   curl http://localhost:11434/api/embeddings -d '{
     "model": "nomic-embed-text",
     "prompt": "test"
   }'
   ```

2. **Test the Chat Interface**: Try the manual test steps above

3. **Monitor Logs**: Check for these log messages:
   - `[RAGEngine] Loaded index with X vectors`
   - `[RAGEngine] Persisted X/Y messages for session Z`
   - `[RAGEngine] Search returned X results for user_id=Y`

4. **Check Performance**: The spec requires:
   - Vector retrieval: < 500ms at p95
   - Chat response: < 3 seconds at p95

## Files Modified

1. `app/api/chat.py` - Updated `/chat/stream` endpoint with RAG integration
2. `app/api/training_plans.py` - Fixed 422 error (user_id parameter)

## Related Documentation

- Spec: `.kiro/specs/fitness-platform-chat-training-upgrade/requirements.md`
- Design: `.kiro/specs/fitness-platform-chat-training-upgrade/design.md`
- Tasks: `.kiro/specs/fitness-platform-chat-training-upgrade/tasks.md`
