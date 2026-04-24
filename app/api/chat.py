"""Chat API endpoints for AI coach conversations."""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import json

from app.limiter import limiter

from app.database import get_db
from app.schemas.chat_schemas import (
    SessionCreate, SessionResponse, SessionWithMessages,
    MessageCreate, MessageResponse
)

from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.athlete import Athlete
from app.services.chat_session_service import ChatSessionService
from app.services.rag_engine import RAGEngine

router = APIRouter()


def get_session_service(db: Session = Depends(get_db)) -> ChatSessionService:
    """
    Dependency injection for ChatSessionService.

    Creates a new ChatSessionService instance with RAG engine.
    """
    rag_engine = RAGEngine(db)
    return ChatSessionService(db, rag_engine)


@router.get("/sessions", response_model=List[SessionResponse], summary="List chat sessions")
async def list_sessions(
    athlete_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Retrieve all chat sessions with optional filtering.

    **Query Parameters:**
    - `athlete_id`: Filter by athlete identifier
    - `limit`: Maximum number of sessions to return (default: 50)

    **Returns:**
    - List of sessions ordered by update time (most recent first)
    - Includes message count for each session
    """
    query = db.query(
        ChatSession,
        func.count(ChatMessage.id).label('message_count')
    ).outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)

    if athlete_id:
        query = query.filter(ChatSession.athlete_id == athlete_id)

    query = query.group_by(ChatSession.id).order_by(ChatSession.updated_at.desc()).limit(limit)

    results = query.all()

    sessions = []
    for session, message_count in results:
        session_dict = {
            'id': str(session.id),
            'athlete_id': str(session.athlete_id) if session.athlete_id else None,
            'title': session.title,
            'created_at': session.created_at,
            'updated_at': session.updated_at,
            'message_count': message_count
        }
        sessions.append(session_dict)

    return sessions


@router.post("/sessions", response_model=SessionResponse, summary="Create a new chat session")
async def create_session(
    session: SessionCreate,
    athlete_id: Optional[int] = None,
    db: Session = Depends(get_db),
    session_service: ChatSessionService = Depends(get_session_service)
):
    """
    Create a new chat session.

    **Fields:**
    - `title`: Optional session title (default: "New Chat")
    - `athlete_id`: Optional athlete identifier

    **Returns:**
    - Created session with ID and timestamps
    """
    # Create default athlete if none exists and no athlete_id provided
    if athlete_id is None:
        # Check if default athlete exists
        default_athlete = db.query(Athlete).filter(Athlete.id == 1).first()
        if not default_athlete:
            # Create default athlete
            default_athlete = Athlete(
                id=1,
                name="Default Athlete",
                email=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(default_athlete)
            db.commit()
        athlete_id = 1

    # Use ChatSessionService to create session
    session_id = session_service.create_session(
        athlete_id=athlete_id,
        title=session.title or "New Chat"
    )

    # Retrieve created session for response
    new_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    return {
        'id': str(new_session.id),
        'athlete_id': str(new_session.athlete_id) if new_session.athlete_id else None,
        'title': new_session.title,
        'created_at': new_session.created_at,
        'updated_at': new_session.updated_at,
        'message_count': 0
    }


@router.get("/sessions/{session_id}", response_model=SessionWithMessages, summary="Get session with messages")
async def get_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieve a specific session with all its messages.

    **Parameters:**
    - `session_id`: Session identifier

    **Returns:**
    - Session details with all messages ordered chronologically
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    # Convert messages to response format
    message_responses = []
    for msg in messages:
        message_responses.append({
            'id': str(msg.id),
            'session_id': str(msg.session_id),
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at
        })

    return {
        'id': str(session.id),
        'athlete_id': str(session.athlete_id) if session.athlete_id else None,
        'title': session.title,
        'created_at': session.created_at,
        'updated_at': session.updated_at,
        'message_count': len(messages),
        'messages': message_responses
    }


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse], summary="Get session messages")
async def get_session_messages(
    session_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Retrieve messages for a specific session.

    **Parameters:**
    - `session_id`: Session identifier
    - `limit`: Maximum number of messages to return (default: 50, max: 100)

    **Returns:**
    - List of messages ordered chronologically (oldest first)
    - Limited to most recent messages if limit exceeded
    """
    # Verify session exists
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Limit to max 100 messages
    limit = min(limit, 100)

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.desc()).limit(limit).all()

    # Reverse to get chronological order
    messages.reverse()

    # Convert to response format
    message_responses = []
    for msg in messages:
        message_responses.append({
            'id': str(msg.id),
            'session_id': str(msg.session_id),
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at
        })

    return message_responses


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse, summary="Send a message")
@limiter.limit("100/minute")
async def create_message(
    request: Request,
    session_id: int,
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Send a message in a chat session with RAG-based context retrieval.

    This endpoint:
    1. Retrieves context from active session buffer and vector store (RAG)
    2. Sends message to LLM with retrieved context
    3. Executes any tool calls requested by LLM
    4. Saves and returns the assistant response

    **Parameters:**
    - `session_id`: Session identifier

    **Fields:**
    - `content`: Message content (1-2000 characters)

    **Returns:**
    - The assistant's response message

    **Note:** For streaming responses, use the `/chat/stream` endpoint instead

    Requirements: 1.1, 1.2, 1.3, 1.4, 17.1
    """
    # Verify session exists
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Get athlete_id for user scoping
    athlete_id = session.athlete_id or 1  # Default to 1 if not set

    # Initialize Chat Message Handler with ChatAgent (Phase 3 + Phase 5 LLMAdapter)
    from app.services.llm_client import LLMClient
    from app.services.chat_message_handler import ChatMessageHandler
    from app.services.chat_agent import ChatAgent
    from app.ai.context.chat_context import ChatContextBuilder
    from app.ai.adapter.langchain_adapter import LangChainAdapter

    try:
        llm_client = LLMClient()
        rag_engine = RAGEngine(db)
        session_service = ChatSessionService(db, rag_engine)

        # Build ChatAgent with CE components and LLMAdapter
        context_builder = ChatContextBuilder(db=db, token_budget=32000)
        llm_adapter = LangChainAdapter()
        agent = ChatAgent(
            context_builder=context_builder,
            llm_adapter=llm_adapter,
            db=db,
            llm_client=llm_client,
        )

        # Create thin coordinator handler
        handler = ChatMessageHandler(
            db=db,
            session_service=session_service,
            agent=agent,
            user_id=athlete_id,
            session_id=session_id,
        )

        # Handle message via agent delegation
        response = await handler.handle_message(message.content)

        assistant_content = response['content']

        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            role='user',
            content=message.content,
            created_at=datetime.utcnow()
        )
        db.add(user_message)

        # Save assistant message
        assistant_message = ChatMessage(
            session_id=session_id,
            role='assistant',
            content=assistant_content,
            created_at=datetime.utcnow()
        )
        db.add(assistant_message)

        # Update session timestamp
        session.updated_at = datetime.utcnow()

        # Update session title from first user message if needed
        if session.title == "New Chat":
            session.title = message.content[:50]

        db.commit()
        db.refresh(assistant_message)

        return {
            'id': str(assistant_message.id),
            'session_id': str(assistant_message.session_id),
            'role': assistant_message.role,
            'content': assistant_message.content,
            'created_at': assistant_message.created_at
        }

    except Exception as e:
        print(f"Error processing message with RAG: {e}")
        import traceback
        traceback.print_exc()

        # Fallback to simple response
        assistant_content = "I'm having trouble processing your request right now. Please try again in a moment."

        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            role='user',
            content=message.content,
            created_at=datetime.utcnow()
        )
        db.add(user_message)

        # Save assistant message
        assistant_message = ChatMessage(
            session_id=session_id,
            role='assistant',
            content=assistant_content,
            created_at=datetime.utcnow()
        )
        db.add(assistant_message)

        # Update session timestamp
        session.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(assistant_message)

        return {
            'id': str(assistant_message.id),
            'session_id': str(assistant_message.session_id),
            'role': assistant_message.role,
            'content': assistant_message.content,
            'created_at': assistant_message.created_at
        }


@router.delete("/sessions/{session_id}", summary="Delete a chat session")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    session_service: ChatSessionService = Depends(get_session_service)
):
    """
    Delete a chat session and all its messages.

    Also removes the session from the vector store.

    **Parameters:**
    - `session_id`: Session identifier

    **Returns:**
    - Success message

    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Use ChatSessionService to delete session
    session_service.delete_session(session_id)

    return {"success": True, "message": f"Session {session_id} deleted"}


@router.post("/sessions/{session_id}/persist", summary="Persist session to vector store")
async def persist_session(
    session_id: int,
    eval_score: Optional[float] = None,
    db: Session = Depends(get_db),
    session_service: ChatSessionService = Depends(get_session_service)
):
    """
    Persist a chat session to the vector store for future context retrieval.

    This should be called when a session ends or when the user navigates away.
    The session messages will be embedded and stored in the vector store for
    semantic search in future conversations.

    **Parameters:**
    - `session_id`: Session identifier
    - `eval_score`: Optional evaluation score for the session (0-10)

    **Returns:**
    - Success message with count of persisted messages

    Requirements: 1.4, 1.5, 1.6
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Get message count for response
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).all()

    if not messages:
        return {
            "success": True,
            "message": "No messages to persist",
            "messages_persisted": 0
        }

    try:
        # Load session into service buffer if not already loaded
        session_service.load_session(session_id)

        # Use ChatSessionService to persist session
        session_service.persist_session(session_id, eval_score)

        return {
            "success": True,
            "message": f"Session {session_id} persisted to vector store",
            "messages_persisted": len(messages)
        }

    except Exception as e:
        print(f"Error persisting session to vector store: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to persist session: {str(e)}"
        )


@router.post("/stream", summary="Stream chat response")
@limiter.limit("100/minute")
async def stream_chat(
    request: Request,
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Stream a chat response using Server-Sent Events with RAG-based context retrieval.

    This endpoint:
    1. Retrieves context from active session buffer and vector store (RAG)
    2. Streams the LLM response in real-time with retrieved context
    3. Executes any tool calls requested by LLM
    4. Saves messages to database
    5. Returns chunks as they're generated

    **Fields:**
    - `message.content`: User message content
    - `message.session_id`: Session ID for context (required for RAG)

    **Returns:**
    - Server-Sent Events stream with response chunks
    - Final event with "done" type

    **Event Format:**
    ```
    data: {"type": "chunk", "content": "Hello"}

    data: {"type": "done"}
    ```

    Requirements: 1.1, 1.2, 1.3, 1.4, 17.1
    """
    # Get session_id from message body
    session_id = message.session_id

    # If no session_id provided, create a new session
    if not session_id:
        new_session = ChatSession(
            athlete_id=1,  # Default athlete
            title=message.content[:50] if message.content else "New Chat",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        session_id = new_session.id

    # Verify session exists
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Get athlete_id for user scoping
    athlete_id = session.athlete_id or 1

    async def event_generator():
        """Generate Server-Sent Events with RAG integration."""
        try:
            # Initialize Chat Message Handler with ChatAgent (Phase 3 + Phase 5 LLMAdapter)
            from app.services.llm_client import LLMClient
            from app.services.chat_message_handler import ChatMessageHandler
            from app.services.chat_agent import ChatAgent
            from app.ai.context.chat_context import ChatContextBuilder
            from app.ai.adapter.langchain_adapter import LangChainAdapter

            llm_client = LLMClient()
            rag_engine = RAGEngine(db)
            session_service = ChatSessionService(db, rag_engine)

            # Build ChatAgent with CE components and LLMAdapter
            context_builder = ChatContextBuilder(db=db, token_budget=32000)
            llm_adapter = LangChainAdapter()
            agent = ChatAgent(
                context_builder=context_builder,
                llm_adapter=llm_adapter,
                db=db,
                llm_client=llm_client,
            )

            # Create thin coordinator handler
            handler = ChatMessageHandler(
                db=db,
                session_service=session_service,
                agent=agent,
                user_id=athlete_id,
                session_id=session_id,
            )

            # Handle message via agent delegation
            response = await handler.handle_message(message.content)

            assistant_content = response['content']

            # Stream the response in chunks
            chunk_size = 50  # Characters per chunk
            for i in range(0, len(assistant_content), chunk_size):
                chunk = assistant_content[i:i + chunk_size]
                event_data = json.dumps({
                    'type': 'chunk',
                    'content': chunk
                })
                yield f"data: {event_data}\n\n"

            # Save user message
            user_message = ChatMessage(
                session_id=session_id,
                role='user',
                content=message.content,
                created_at=datetime.utcnow()
            )
            db.add(user_message)

            # Save assistant message
            assistant_message = ChatMessage(
                session_id=session_id,
                role='assistant',
                content=assistant_content,
                created_at=datetime.utcnow()
            )
            db.add(assistant_message)

            # Update session timestamp
            session.updated_at = datetime.utcnow()

            # Update session title from first user message if needed
            if session.title == "New Chat":
                session.title = message.content[:50]

            db.commit()

            # Persist session to vector store for future context retrieval
            # This ensures the conversation is available for RAG in future sessions
            try:
                # Get all messages in this session
                all_messages = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id
                ).order_by(ChatMessage.created_at.asc()).all()

                # Persist to vector store (Requirement 1.4, 1.5, 1.6)
                rag_engine.persist_session(
                    user_id=athlete_id,
                    session_id=session_id,
                    messages=all_messages,
                    eval_score=None  # Could be calculated based on conversation quality
                )
                print(f"[Chat API] Persisted session {session_id} to vector store")
            except Exception as e:
                print(f"[Chat API] Warning: Failed to persist session to vector store: {e}")
                # Don't fail the request if persistence fails

            # Send done event
            done_data = json.dumps({'type': 'done', 'session_id': session_id})
            yield f"data: {done_data}\n\n"

        except Exception as e:
            print(f"Error in stream_chat with RAG: {e}")
            import traceback
            traceback.print_exc()

            # Send error event
            error_data = json.dumps({
                'type': 'error',
                'message': str(e)
            })
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
