# Tool Calling Troubleshooting Guide

## Current Issue
The `gpt-oss:20b` model mentions saving goals but doesn't actually call the `save_athlete_goal` tool. This indicates weak or missing tool calling support.

## Quick Fix: Switch to Mistral (Recommended)

Mistral has excellent native tool calling support and will reliably call tools.

### Steps:
1. Update `.env`:
```env
OLLAMA_MODEL=mistral
```

2. Restart your FastAPI server:
```bash
# Stop current server (Ctrl+C)
# Start again
python -m uvicorn app.main:app --reload
```

3. Test in the chat interface - Mistral should now call the tool properly

## Why gpt-oss:20b Doesn't Work Well

The `gpt-oss:20b` model:
- ❌ Has weak or no native tool calling support
- ❌ Understands tools conceptually but doesn't invoke them
- ❌ Will mention "saving" but won't actually call `save_athlete_goal`

The `mistral` model:
- ✅ Has strong native tool calling support
- ✅ Reliably invokes tools when appropriate
- ✅ Smaller size (4.4GB vs 13GB)
- ✅ Faster inference

## Alternative: Implement ReAct Agent (Advanced)

If you really want to use `gpt-oss:20b`, you'd need to implement a ReAct agent that:
1. Parses the model's text output
2. Detects when it wants to call a tool
3. Manually extracts parameters
4. Calls the tool
5. Feeds results back

This is complex and error-prone. **Not recommended.**

## Testing Tool Calling

Run the test script to verify tool calling:

```bash
python test_tool_calling.py
```

This will:
- Test the current model configuration
- Show whether tools are being called
- Provide recommendations

## Model Comparison

| Model | Size | Tool Calling | Speed | Recommendation |
|-------|------|--------------|-------|----------------|
| mistral | 4.4GB | ✅ Excellent | Fast | **Use this** |
| gpt-oss:20b | 13GB | ❌ Poor | Slower | Avoid for tool calling |
| llama3 | 4.7GB | ✅ Good | Fast | Alternative option |
| qwen2.5 | 4.7GB | ✅ Good | Fast | Alternative option |

## Current Configuration

Your `.env` is now set to:
```env
LLM_TYPE=ollama
OLLAMA_ENDPOINT=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
```

**Recommended change:**
```env
OLLAMA_MODEL=mistral
```

## Verification Steps

1. **Check model is loaded:**
```bash
docker exec fitness-ollama ollama list
```

2. **Test tool calling:**
```bash
python test_tool_calling.py
```

3. **Check server logs:**
Look for these messages:
- `[LangChain] Tool calls detected: 1` ✅ Good
- `[LangChain] No tool calls detected` ❌ Bad
- `[LangChain] WARNING: LLM mentioned saving goal but didn't call tool` ❌ Bad

## Next Steps

1. Switch to `mistral` in `.env`
2. Restart FastAPI server
3. Test in chat interface with: "I want to lose 5kg from 90kg to 85kg by May 30th"
4. Verify the goal is saved (check logs for "Tool calls detected")

## Still Having Issues?

If Mistral still doesn't call tools:
1. Check LangChain version: `pip show langchain-ollama`
2. Verify Ollama is running: `docker ps`
3. Check server logs for errors
4. Try pulling Mistral again: `docker exec fitness-ollama ollama pull mistral`
