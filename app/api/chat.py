"""Chat API endpoints for AI coach conversations."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import uuid
import json

from app.database import get_db
from app.models.base import Base
from app.schemas.chat_schemas import (
    SessionCreate, SessionResponse, SessionWithMessages,
    MessageCreate, MessageResponse
)
# Try LangChain service first, fall back to regular service
try:
    from app.config import get_settings
    settings = get_settings()
    
    if settings.LLM_TYPE == "lm-studio":
        # Use native LM Studio service (uses /api/v1/chat endpoint)
        from app.services.lmstudio_chat_service import LMStudioChatService as ChatService
        print("[Chat API] Using LM Studio native chat service")
    else:
        # Use LangChain service for Ollama
        from app.services.langchain_chat_service import LangChainChatService as ChatService
        print("[Chat API] Using LangChain-based chat service with agentic tool calling")
except ImportError as e:
    print(f"[Chat API] LangChain not available ({e}), using regular chat service")
    from app.services.chat_service import ChatService

# Import chat models
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.athlete import Athlete

router = APIRouter()


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
    db: Session = Depends(get_db)
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
    
    new_session = ChatSession(
        athlete_id=athlete_id,
        title=session.title or "New Chat",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
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
async def create_message(
    session_id: int,
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Send a message in a chat session.
    
    This endpoint:
    1. Saves the user message
    2. Sends it to the LLM for processing
    3. Saves and returns the assistant response
    
    **Parameters:**
    - `session_id`: Session identifier
    
    **Fields:**
    - `content`: Message content (1-2000 characters)
    
    **Returns:**
    - The assistant's response message
    
    **Note:** For streaming responses, use the `/chat/stream` endpoint instead
    """
    # Verify session exists
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    # Save user message
    user_message = ChatMessage(
        session_id=session_id,
        role='user',
        content=message.content,
        created_at=datetime.utcnow()
    )
    db.add(user_message)
    
    # Get conversation history
    chat_service = ChatService(db)
    prev_messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).limit(10).all()
    
    messages = []
    for msg in prev_messages:
        messages.append({
            'role': msg.role,
            'content': msg.content
        })
    
    # Add current user message
    messages.append({
        'role': 'user',
        'content': message.content
    })
    
    # Get LLM response
    try:
        response = await chat_service.get_chat_response(messages)
        assistant_content = response.get('content', 'I apologize, but I encountered an error processing your request.')
    except Exception as e:
        print(f"Error getting LLM response: {e}")
        assistant_content = "I'm having trouble connecting to my AI brain right now. Please try again in a moment."
    
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


@router.delete("/sessions/{session_id}", summary="Delete a chat session")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a chat session and all its messages.
    
    **Parameters:**
    - `session_id`: Session identifier
    
    **Returns:**
    - Success message
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    # Delete all messages in session (cascade should handle this, but explicit is better)
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    
    # Delete session
    db.delete(session)
    db.commit()
    
    return {"success": True, "message": f"Session {session_id} deleted"}


@router.post("/stream", summary="Stream chat response")
async def stream_chat(
    message: MessageCreate,
    session_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Stream a chat response using Server-Sent Events.
    
    This endpoint:
    1. Takes a user message
    2. Streams the LLM response in real-time
    3. Returns chunks as they're generated
    
    **Fields:**
    - `message`: User message content
    - `session_id`: Optional session ID for context
    
    **Returns:**
    - Server-Sent Events stream with response chunks
    - Final event with "done" type
    
    **Event Format:**
    ```
    data: {"type": "chunk", "content": "Hello"}
    
    data: {"type": "done"}
    ```
    """
    chat_service = ChatService(db)
    
    # Build conversation history
    messages = []
    
    # Load previous messages if session_id provided
    if session_id:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            prev_messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).limit(10).all()
            
            for msg in prev_messages:
                messages.append({
                    'role': msg.role,
                    'content': msg.content
                })
    
    # Add current user message
    messages.append({
        'role': 'user',
        'content': message.content
    })
    
    async def event_generator():
        """Generate Server-Sent Events."""
        try:
            async for chunk in chat_service.stream_chat_response(messages):
                # Send chunk as SSE
                event_data = json.dumps({
                    'type': 'chunk',
                    'content': chunk
                })
                yield f"data: {event_data}\n\n"
            
            # Send done event
            done_data = json.dumps({'type': 'done'})
            yield f"data: {done_data}\n\n"
            
        except Exception as e:
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
