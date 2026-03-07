# LangChain Tool Calling Integration Guide

## What Was Done

I've integrated LangChain for more reliable tool calling in the fitness coach chat. The system now supports both Ollama and LM Studio backends.

### 1. LangChain Chat Service (`app/services/langchain_chat_service.py`)
- Uses `langchain-ollama` for Ollama backend
- Uses `langchain-openai` for LM Studio (OpenAI-compatible) backend
- Automatically selects backend based on `LLM_TYPE` in `.env`
- Implements `save_athlete_goal` tool using `@langchain_tool` decorator
- Binds tools to the LLM using `bind_tools()`
- Handles tool execution and returns results to the LLM
- Added comprehensive logging for debugging

### 2. Improvements Made
- **Multi-backend support**: Works with both Ollama and LM Studio
- **Fixed Unicode encoding issue**: Added `encoding='utf-8'` when reading system prompt (Windows compatibility)
- **Enhanced system prompt**: Made it more explicit about WHEN to call the tool
- **Better logging**: Added detailed logs to track tool calling behavior
- **Fallback detection**: Warns if LLM mentions saving but doesn't call the tool

### 3. Chat API Integration (`app/api/chat.py`)
- Automatically uses LangChain service if available
- Falls back to regular service if LangChain not installed
- No changes needed to frontend

## Setup Instructions

### Option A: Using LM Studio (Recommended for Tool Calling)

LM Studio provides better tool calling support through its OpenAI-compatible API.

1. **Download and Install LM Studio**
   - Download from: https://lmstudio.ai/
   - Install and launch the application

2. **Download a Model**
   - In LM Studio, go to the "Discover" tab
   - Search for and download: `openai/gpt-oss-20b` (or any other model you prefer)
   - Wait for the download to complete

3. **Start the Local Server**
   - Go to the "Local Server" tab in LM Studio
   - Select your downloaded model
   - Click "Start Server"
   - The server will start on `http://localhost:1234`

4. **Configure the Application**
   
   Update your `.env` file:
   ```env
   LLM_TYPE=lm-studio
   OLLAMA_ENDPOINT=http://localhost:1234
   OLLAMA_MODEL=openai/gpt-oss-20b
   ```
   
   Note: Use `http://localhost:1234` without `/v1` - LangChain adds it automatically.

5. **Install Dependencies**
   ```bash
   uv pip install langchain-openai
   ```

6. **Start the FastAPI Server**
   ```bash
   uvicorn app.main:app --reload
   ```

### Option B: Using Ollama

1. **Install Ollama**
   - Download from: https://ollama.ai/
   - Install and start the service

2. **Pull a Model**
   ```bash
   ollama pull mistral
   # Or try these for better tool calling:
   ollama pull mistral-openorca
   ollama pull llama2:13b
   ```

3. **Configure the Application**
   
   Update your `.env` file:
   ```env
   LLM_TYPE=ollama
   OLLAMA_ENDPOINT=http://localhost:11434
   OLLAMA_MODEL=mistral
   ```

4. **Install Dependencies**
   ```bash
   uv pip install langchain-ollama
   ```

5. **Start the FastAPI Server**
   ```bash
   uvicorn app.main:app --reload
   ```

## How to Test

### Test Scenario 1: Complete Information in First Message

Open the chat interface (http://localhost:8000/chat.html) and send this message:

```
I want to lose weight for the bike Posidonia Tour. It is a route of 70km with 600m elevation gain. Now I am at 90.5kg. I want to be 85kg until May 30 that is the race day. I will participate in the amateur group.
```

**Expected behavior:**
- LLM should recognize all required information is present
- LLM should call `save_athlete_goal` tool with:
  - `goal_type`: "weight_loss"
  - `target_value`: 85
  - `target_date`: "2026-05-30"
  - `description`: Detailed description including current weight, target, event details
- LLM should confirm the goal was saved

**Check the server logs** for:
```
[LangChain] Initializing with LM Studio/OpenAI backend
[LangChain] Using base_url: http://localhost:1234
[LangChain] Backend: lm-studio, Endpoint: http://localhost:1234, Model: openai/gpt-oss-20b
[LangChain] Tool calls detected: 1
[LangChain] Executing tool: save_athlete_goal
[LangChain] Tool result: ✅ Goal saved! ID: ...
```

### Test Scenario 2: Gradual Information Gathering

Send messages one at a time:

1. "I want to lose weight"
2. "I'm 90.5kg now and want to get to 85kg"
3. "I want to achieve this by May 30th for a cycling race"

**Expected behavior:**
- LLM asks clarifying questions after messages 1 and 2
- LLM calls tool after message 3 when all info is gathered

### Test Scenario 3: Check Saved Goals

After a goal is saved, check the database:

```bash
python -c "from app.database import SessionLocal; from app.models.athlete_goal import AthleteGoal; db = SessionLocal(); goals = db.query(AthleteGoal).all(); print(f'Found {len(goals)} goals'); [print(f'- {g.goal_type}: {g.description}') for g in goals]"
```

Or check via API:
```bash
curl http://localhost:8000/api/goals
```

## Troubleshooting

### Issue 1: LLM Doesn't Call the Tool

**Symptoms:**
- LLM provides advice but doesn't save the goal
- Server logs show: `[LangChain] No tool calls detected`
- Server logs show warning: `LLM mentioned saving goal but didn't call tool`

**Possible causes:**
1. **Model doesn't support tool calling well**
   - Some models have poor tool calling support
   - LM Studio models generally have better support than Ollama models

**Solutions:**

#### Option A: Switch to LM Studio (Recommended)
LM Studio models like `openai/gpt-oss-20b` have excellent tool calling support:

1. Follow the "Setup Instructions > Option A" above
2. Make sure LM Studio server is running
3. Update `.env` to use `LLM_TYPE=lm-studio`
4. Restart the FastAPI server

#### Option B: Try a Different Ollama Model
Some Ollama models have better tool calling support:

```bash
# Try Mistral OpenOrca (better tool calling)
ollama pull mistral-openorca
```

Update `.env`:
```
OLLAMA_MODEL=mistral-openorca
```

Or try other models known for good tool calling:
- `llama2:13b` (larger, better reasoning)
- `codellama:13b` (good at structured outputs)
- `mixtral` (if you have enough RAM)

#### Option B: Use Manual Confirmation UI
If models continue to have issues, implement a manual confirmation flow:

1. LLM outputs goal details in a structured format
2. Frontend parses the response and shows a "Save Goal" button
3. User clicks button to confirm and save

This is more reliable but less "agentic".

#### Option C: Use Structured Output Parsing
Instead of tool calling, ask LLM to output JSON:

```python
# In system prompt:
"When you have all goal information, output it in this JSON format:
{
  \"action\": \"save_goal\",
  \"goal_type\": \"weight_loss\",
  \"target_value\": 85,
  \"target_date\": \"2026-05-30\",
  \"description\": \"...\"
}
"
```

Then parse the JSON and call the tool manually.

### Issue 2: Unicode Encoding Error

**Symptoms:**
```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d
```

**Solution:**
✅ Already fixed! The system prompt file is now read with `encoding='utf-8'`.

### Issue 3: LM Studio Connection Error

**Symptoms:**
```
Connection refused or timeout
openai.NotFoundError: 404 page not found
```

**Solutions:**

1. **Make sure LM Studio server is running**:
   - Open LM Studio
   - Go to "Local Server" tab (↔️ icon)
   - Make sure a model is selected in the dropdown
   - Click "Start Server" if it's not already running
   - You should see "Server running on http://localhost:1234"

2. **Verify the model is loaded**:
   - In LM Studio's "Local Server" tab, check that `openai/gpt-oss-20b` (or your chosen model) is selected
   - If not, select it from the dropdown
   - Wait for it to load (you'll see a loading indicator)

3. **Test the endpoint manually**:
   ```bash
   curl http://localhost:1234/v1/models
   ```
   You should see a JSON response with your loaded model.

4. **Check the endpoint in `.env`**:
   - Should be: `OLLAMA_ENDPOINT=http://localhost:1234`
   - NOT: `http://localhost:1234/v1` (LangChain adds `/v1` automatically)

5. **Restart the FastAPI server** after changing `.env`:
   ```bash
   # Stop the server (Ctrl+C)
   # Then start it again
   uvicorn app.main:app --reload
   ```

6. **Check LM Studio logs**:
   - In LM Studio's "Local Server" tab, check the logs at the bottom
   - Look for any error messages or connection attempts

### Issue 4: Ollama Connection Error

**Symptoms:**
```
[Errno 11001] getaddrinfo failed
```

**Solutions:**
1. Make sure Ollama is running: `ollama serve`
2. Check the endpoint in `.env`: `OLLAMA_ENDPOINT=http://localhost:11434`
3. Test connection: `curl http://localhost:11434/api/tags`

### Issue 5: Tool Execution Fails

**Symptoms:**
- Tool is called but returns error
- Server logs show: `❌ Failed: ...`

**Check:**
1. Goal parameters are valid (see `app/services/goal_service.py` for validation rules)
2. Database is accessible
3. Migration 006 was run successfully

## Monitoring Tool Calls

The server logs now include detailed information about tool calling:

```
[LangChain] Initializing with LM Studio/OpenAI backend
[LangChain] Using base_url: http://localhost:1234
[LangChain] Backend: lm-studio, Endpoint: http://localhost:1234, Model: openai/gpt-oss-20b
[LangChain] Initialized with 1 tools
[LangChain] Invoking LLM with 2 messages
[LangChain] Tools available: ['save_athlete_goal']
[LangChain] Response type: <class 'langchain_core.messages.ai.AIMessage'>
[LangChain] Response has tool_calls: True
[LangChain] Tool calls: [{'name': 'save_athlete_goal', 'args': {...}, 'id': '...'}]
[LangChain] Tool calls detected: 1
[LangChain] Executing tool: save_athlete_goal
[LangChain] Args: {'goal_type': 'weight_loss', 'target_value': 85, ...}
[LangChain] Tool result: ✅ Goal saved! ID: abc-123
```

Watch these logs when testing to understand what's happening.

## Next Steps

1. **Set up LM Studio** (recommended for best tool calling):
   - Download and install LM Studio
   - Download the `openai/gpt-oss-20b` model
   - Start the local server
   - Update `.env` with LM Studio settings
   - Restart FastAPI server

2. **Test the integration**: Use the test scenarios above

3. **Check the logs**: Server logs will show exactly what's happening

4. **Verify goals are saved**: Check the database or API to confirm goals are persisted

## Why LM Studio is Better for Tool Calling

LM Studio models (especially those with "openai" in the name) are specifically trained to work with OpenAI's function calling format, which LangChain uses. This means:

- **More reliable tool detection**: The model understands when to call tools
- **Better parameter extraction**: Correctly extracts goal_type, target_value, etc.
- **Consistent behavior**: Less variation in responses
- **OpenAI compatibility**: Uses the same API format as OpenAI's GPT models

The `openai/gpt-oss-20b` model you mentioned is an excellent choice for this use case!

## Alternative: Manual Confirmation UI

If tool calling continues to be unreliable, we can implement a hybrid approach:

1. LLM gathers information through conversation
2. LLM outputs goal details in a structured format (JSON or markdown)
3. Frontend displays a "Save Goal" button with the parsed details
4. User reviews and confirms
5. Frontend calls the API directly to save

This is less "agentic" but more reliable and gives users control.

Would you like me to implement this fallback approach?
