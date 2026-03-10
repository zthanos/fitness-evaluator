# Session Management Fix

## Problem
The chat frontend was creating a new session for every message instead of reusing the existing session. This caused:
- Loss of conversation context
- Multiple sessions with single messages
- Broken chat history

## Root Cause
The `/chat/stream` endpoint had a parameter mismatch:
- **Backend expected**: `session_id` as a separate query/path parameter
- **Frontend sent**: `session_id` in the JSON request body

FastAPI couldn't extract `session_id` from the body because it wasn't defined in the `MessageCreate` schema, so it always defaulted to `None`, triggering new session creation.

## Solution

### 1. Updated `app/schemas/chat_schemas.py`
Added `session_id` field to `MessageCreate` schema:
```python
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[int] = Field(None, description="Session identifier")
```

### 2. Updated `app/api/chat.py`
Modified `/chat/stream` endpoint to extract `session_id` from message body:
```python
async def stream_chat(
    message: MessageCreate,  # session_id is now part of this
    db: Session = Depends(get_db)
):
    # Get session_id from message body
    session_id = message.session_id
    
    # Only create new session if session_id is None
    if not session_id:
        # Create new session...
```

## How It Works Now

### Frontend Flow (Correct)
1. User clicks "New Chat" → Creates new session via API
2. User sends first message → Includes `session_id` in request body
3. User sends subsequent messages → Same `session_id` reused
4. All messages belong to the same session ✅

### Backend Flow (Fixed)
1. Receives message with `session_id` in body
2. Extracts `session_id` from `MessageCreate` object
3. If `session_id` exists → Uses existing session
4. If `session_id` is None → Creates new session
5. Saves messages to the correct session ✅

## Testing
After restarting the server:
1. Click "New Chat" button
2. Send a message (e.g., "I want to lose 5kg")
3. Send another message (e.g., "What should I do?")
4. Check the session list - should show ONE session with 4 messages (2 user + 2 assistant)
5. Refresh the page and load the session - all messages should be there

## Related Files
- `app/schemas/chat_schemas.py` - Added `session_id` to MessageCreate
- `app/api/chat.py` - Updated stream_chat endpoint
- `public/js/coach-chat.js` - Frontend already correct (no changes needed)
