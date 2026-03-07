# Quick Setup: LM Studio with Tool Calling

## What Changed

Your fitness coach chat now supports **LM Studio** in addition to Ollama. LM Studio provides much better tool calling support, which means the AI will reliably save goals when you ask it to.

## Setup Steps

### 1. Download LM Studio
- Go to: https://lmstudio.ai/
- Download and install for Windows
- Launch the application

### 2. Download the Model
- In LM Studio, click the "Discover" tab (🔍 icon)
- Search for: `openai/gpt-oss-20b`
- Click "Download" and wait for it to complete

### 3. Start the Server
- Click the "Local Server" tab (↔️ icon)
- Select `openai/gpt-oss-20b` from the model dropdown
- Click "Start Server"
- You should see: "Server running on http://localhost:1234"

### 4. Update Your Configuration

Your `.env` file has already been updated with:
```env
LLM_TYPE=lm-studio
OLLAMA_ENDPOINT=http://localhost:1234
OLLAMA_MODEL=openai/gpt-oss-20b
```

Note: The endpoint is `http://localhost:1234` without `/v1` because LangChain adds that automatically.

### 5. Start the Application

```bash
# Make sure you're in the project directory
uvicorn app.main:app --reload
```

You should see in the logs:
```
[LangChain] Initializing with LM Studio/OpenAI backend
[LangChain] Using base_url: http://localhost:1234
[LangChain] Backend: lm-studio, Endpoint: http://localhost:1234, Model: openai/gpt-oss-20b
```

## Test It Out

1. Open http://localhost:8000/chat.html
2. Send this message:
   ```
   I want to lose weight for the bike Posidonia Tour. It is a route of 70km with 600m elevation gain. Now I am at 90.5kg. I want to be 85kg until May 30 that is the race day. I will participate in the amateur group.
   ```
3. The AI should:
   - Understand your goal
   - Call the `save_athlete_goal` tool automatically
   - Confirm the goal was saved with a ✅ message

4. Check the server logs for:
   ```
   [LangChain] Tool calls detected: 1
   [LangChain] Executing tool: save_athlete_goal
   [LangChain] Tool result: ✅ Goal saved! ID: ...
   ```

5. Verify the goal was saved:
   ```bash
   curl http://localhost:8000/api/goals
   ```

## Why This is Better

**Before (Ollama with Mistral):**
- ❌ Model often didn't call the tool
- ❌ Just provided advice instead of saving
- ❌ Inconsistent behavior

**After (LM Studio with openai/gpt-oss-20b):**
- ✅ Reliably detects when to call tools
- ✅ Correctly extracts parameters
- ✅ Consistent, predictable behavior
- ✅ OpenAI-compatible API format

## Troubleshooting

### "404 page not found" Error

This usually means LM Studio's server isn't properly configured. Here's how to fix it:

1. **Open LM Studio** and go to the "Local Server" tab (↔️ icon)

2. **Make sure a model is selected**:
   - Look at the model dropdown at the top
   - It should show `openai/gpt-oss-20b` (or your chosen model)
   - If it says "No model loaded", select your model from the dropdown

3. **Start the server**:
   - Click the "Start Server" button
   - Wait for it to show "Server running on http://localhost:1234"
   - The button should change to "Stop Server"

4. **Test the connection**:
   - In LM Studio, you should see a green "Running" indicator
   - Try this command in your terminal:
     ```bash
     curl http://localhost:1234/v1/models
     ```
   - You should get a JSON response with your model info

5. **Restart your FastAPI server**:
   ```bash
   # Stop it with Ctrl+C
   # Then start again
   uvicorn app.main:app --reload
   ```

6. **Try the chat again**

### "Connection refused" error
- Make sure LM Studio server is running (green "Running" indicator)
- Check that it's on port 1234
- Try clicking "Stop Server" then "Start Server" again

### Model not found
- Make sure you downloaded `openai/gpt-oss-20b` in the Discover tab
- Wait for the download to complete (can take a few minutes)
- Restart LM Studio if needed

### Tool not being called
- Check server logs for `[LangChain]` messages
- Make sure you're using `LLM_TYPE=lm-studio` in `.env`
- Restart the FastAPI server after changing `.env`

## Settings UI

You can also configure LM Studio through the Settings page:

1. Go to http://localhost:8000/settings.html
2. Scroll to "LLM Configuration"
3. Select:
   - **LLM Type**: LM Studio
   - **Endpoint Preset**: LM Studio (http://localhost:1234/v1)
   - **Model Name**: openai/gpt-oss-20b
4. Click "Test Connection" to verify
5. Click "Save Settings"

Note: You'll still need to update the `.env` file and restart the server for changes to take effect.

## Next Steps

Once you confirm tool calling is working:
1. Continue testing with different goal scenarios
2. Try the gradual information gathering flow
3. Check that goals appear in the Settings page under "Goals"
4. Verify the chat experience feels natural and helpful

For more details, see `LANGCHAIN_TOOL_CALLING_GUIDE.md`.
