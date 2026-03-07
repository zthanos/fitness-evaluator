"""Pydantic schemas for chat API endpoints."""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class MessageCreate(BaseModel):
    """Schema for creating a chat message."""
    content: str = Field(..., min_length=1, max_length=2000, description="Message content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "I want to set a new fitness goal"
            }
        }


class MessageResponse(BaseModel):
    """Schema for message response."""
    id: str = Field(..., description="Message identifier")
    session_id: str = Field(..., description="Session identifier")
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "msg_123",
                "session_id": "session_456",
                "role": "user",
                "content": "I want to set a new fitness goal",
                "created_at": "2024-03-15T10:30:00"
            }
        }


class SessionCreate(BaseModel):
    """Schema for creating a chat session."""
    title: Optional[str] = Field(None, max_length=200, description="Session title")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Goal Setting Chat"
            }
        }


class SessionResponse(BaseModel):
    """Schema for session response."""
    id: str = Field(..., description="Session identifier")
    athlete_id: Optional[str] = Field(None, description="Athlete identifier")
    title: str = Field(..., description="Session title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: Optional[int] = Field(None, description="Number of messages in session")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "session_456",
                "athlete_id": None,
                "title": "Goal Setting Chat",
                "created_at": "2024-03-15T10:30:00",
                "updated_at": "2024-03-15T10:35:00",
                "message_count": 5
            }
        }


class SessionWithMessages(SessionResponse):
    """Schema for session with messages."""
    messages: List[MessageResponse] = Field(default_factory=list, description="Session messages")
    
    class Config:
        from_attributes = True
