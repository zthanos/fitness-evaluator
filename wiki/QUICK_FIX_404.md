# Quick Fix for 404 Error

The 404 error you're seeing means LM Studio's API endpoint isn't responding correctly. Here's the quick fix:

## What I Changed

1. **Updated endpoint handling** in `langchain_chat_service.py`:
   - Now automatically removes `/v1` from the endpoint since LangChain adds it
   - Added logging to show the actual base_url being used

2. **Updated `.env`**:
   - Changed from `http://localhost:1234/v1` to `http://localhost:1234`
   - LangChain's `ChatOpenAI` automatically adds `/v1/chat/completions`

3. **Updated all documentation** to reflect the correct endpoint format

## Steps to Fix Your Issue

### 1. Check LM Studio is Running Properly

Open LM Studio and verify:

- ✅ You're on the "Local Server" tab (↔️ icon)
- ✅ A model is selected in the dropdown (should show `openai/gpt-oss-20b`)
- ✅ Server is started (green "Running" indicator)
- ✅ Shows "Server running on http://localhost:1234"

**If the model dropdown is empty or says "No model loaded":**
1. Go to the "Discover" tab (🔍 icon)
2. Search for `openai/gpt-oss-20b`
3. Download it (if not already downloaded)
4. Go back to "Local Server" tab
5. Select the model from the dropdown
6. Click "Start Server"

### 2. Test the Endpoint

Open a terminal and run:
```bash
curl http://localhost:1234/v1/models
```

**Expected response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "openai/gpt-oss-20b",
      ...
    }
  ]
}
```

**If you get an error:**
- Make sure LM Studio server is actually running
- Try stopping and starting the server in LM Studio
- Check if another application is using port 1234

### 3. Restart Your FastAPI Server

The `.env` file has been updated, so you need to restart:

```bash
# Stop the server (Ctrl+C in the terminal where it's running)
# Then start it again
uvicorn app.main:app --reload
```

### 4. Check the Logs

When the server starts, you should see:
```
[LangChain] Initializing with LM Studio/OpenAI backend
[LangChain] Using base_url: http://localhost:1234
[LangChain] Backend: lm-studio, Endpoint: http://localhost:1234, Model: openai/gpt-oss-20b
```

### 5. Test the Chat

1. Go to http://localhost:8000/chat.html
2. Send your weight loss goal message
3. Watch the server logs for tool calling

## Common Issues

### Issue: Model not loaded in LM Studio
**Solution**: Select the model from the dropdown in the "Local Server" tab

### Issue: Port 1234 already in use
**Solution**: 
- Close other applications that might be using port 1234
- Or change the port in LM Studio settings and update `.env`

### Issue: Still getting 404
**Solution**:
1. In LM Studio, click "Stop Server" then "Start Server"
2. Wait for it to fully start (green indicator)
3. Test with curl command above
4. Restart FastAPI server

## Alternative: Try a Different Model

If `openai/gpt-oss-20b` isn't working, try these models in LM Studio:

1. `TheBloke/Mistral-7B-Instruct-v0.2-GGUF`
2. `TheBloke/OpenHermes-2.5-Mistral-7B-GGUF`
3. Any model with "openai" or "gpt" in the name (better tool calling support)

To switch models:
1. Download the new model in LM Studio's "Discover" tab
2. Select it in the "Local Server" tab
3. Update `OLLAMA_MODEL` in `.env` to match the model name
4. Restart FastAPI server

## Need More Help?

See the full guides:
- `LM_STUDIO_SETUP.md` - Complete setup instructions
- `LANGCHAIN_TOOL_CALLING_GUIDE.md` - Comprehensive troubleshooting

Or check LM Studio's logs in the "Local Server" tab for specific error messages.
