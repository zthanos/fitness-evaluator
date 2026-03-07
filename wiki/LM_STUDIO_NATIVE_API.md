# LM Studio Native API Integration

## What Changed

I discovered that LM Studio uses its own API format (`/api/v1/chat`) instead of the OpenAI-compatible format (`/v1/chat/completions`). I've created a custom LM Studio service that works with this native API.

## New Service: LMStudioChatService

Created `app/services/lmstudio_chat_service.py` which:
- Uses LM Studio's native `/api/v1/chat` endpoint
- Implements heuristic-based goal extraction (since LM Studio doesn't support native tool calling)
- Automatically detects when a goal should be saved based on conversation context
- Extracts goal parameters (type, target weight, target date) from the user's message

## How It Works

1. **User sends a message** with goal information (e.g., "I want to lose weight from 90.5kg to 85kg by May 30")

2. **LM Studio responds** with coaching advice

3. **Service detects goal intent** by looking for keywords like "want to", "goal", "lose weight", etc.

4. **Service extracts parameters**:
   - Goal type: weight_loss, weight_gain, performance, etc.
   - Target value: Extracted from patterns like "85kg"
   - Target date: Extracted from patterns like "May 30"
   - Description: The full user message

5. **Goal is saved automatically** if all required information is present

6. **Confirmation is added** to the LLM's response

## Configuration

Your `.env` is already configured correctly:
```env
LLM_TYPE=lm-studio
OLLAMA_ENDPOINT=http://localhost:1234
OLLAMA_MODEL=openai/gpt-oss-20b
```

Note: The endpoint is `http://localhost:1234` (the service adds `/api/v1/chat` automatically)

## Testing

1. **Make sure LM Studio is running**:
   - Open LM Studio
   - Go to "Local Server" tab
   - Model should be loaded (`openai/gpt-oss-20b`)
   - Server should be running (green indicator)

2. **Restart your FastAPI server**:
   ```bash
   uvicorn app.main:app --reload
   ```

3. **Check the logs** - you should see:
   ```
   [Chat API] Using LM Studio native chat service
   [LMStudio] Initialized
   [LMStudio] Endpoint: http://localhost:1234/api/v1/chat
   [LMStudio] Model: openai/gpt-oss-20b
   ```

4. **Test the chat** at http://localhost:8000/chat.html

5. **Send your goal message**:
   ```
   I want to lose weight for the bike Posidonia Tour. It is a route of 70km with 600m elevation gain. Now I am at 90.5kg. I want to be 85kg until May 30 that is the race day. I will participate in the amateur group.
   ```

6. **Watch the server logs** for:
   ```
   [LMStudio] Sending request to http://localhost:1234/api/v1/chat
   [LMStudio] Response received: ...
   [LMStudio] Detected goal-setting intent, attempting to extract goal details
   [LMStudio] Extracted goal data: {'goal_type': 'weight_loss', 'target_value': 85.0, ...}
   [LMStudio] Goal saved successfully: <goal-id>
   ```

## Limitations

Since LM Studio doesn't support native tool calling like OpenAI's API, this implementation uses heuristic-based extraction:

### What Works Well:
- ✅ Detecting goal-setting intent
- ✅ Extracting weight goals (e.g., "85kg")
- ✅ Extracting dates (e.g., "May 30")
- ✅ Determining goal type (weight_loss, performance, etc.)

### What Might Need Refinement:
- ⚠️ Complex date formats might not be parsed correctly
- ⚠️ Ambiguous goal types might be misclassified
- ⚠️ Goals without explicit numbers might not be extracted

### Future Improvements:
1. **Structured Output**: Ask LM Studio to output JSON with goal parameters
2. **Confirmation UI**: Show extracted parameters and ask user to confirm before saving
3. **Multi-turn Extraction**: Ask follow-up questions if information is missing

## Troubleshooting

### Goal Not Being Saved

**Check the logs** for:
```
[LMStudio] Detected goal-setting intent
```

If you don't see this, the service didn't detect goal-setting intent. This could be because:
- The user message doesn't contain goal keywords
- The LLM response doesn't indicate readiness to save

**Solution**: Make your goal message more explicit:
```
I want to set a goal: lose weight from 90.5kg to 85kg by May 30
```

### Wrong Goal Parameters Extracted

**Check the logs** for:
```
[LMStudio] Extracted goal data: {...}
```

If the parameters are wrong, you can:
1. Edit the goal in the Settings page
2. Delete and recreate with a clearer message
3. Improve the extraction logic in `_extract_goal_from_response()`

### LM Studio Connection Error

If you see connection errors, verify:
1. LM Studio is running
2. Server is started in "Local Server" tab
3. Model is loaded
4. Endpoint is `http://localhost:1234` (not `http://localhost:1234/v1`)

## Comparison: LM Studio vs Ollama

| Feature | LM Studio (Native API) | Ollama (LangChain) |
|---------|------------------------|---------------------|
| Setup Complexity | Medium (UI required) | Easy (CLI only) |
| Tool Calling | Heuristic-based | Native support |
| Accuracy | Good for explicit goals | Excellent |
| Speed | Fast | Fast |
| Reliability | Good | Excellent |

**Recommendation**: 
- Use LM Studio if you prefer the UI and visual model management
- Use Ollama if you want more reliable tool calling and simpler setup

## Next Steps

1. Test the integration with your goal message
2. Check if the goal is saved correctly
3. Verify the goal appears in Settings page
4. If it works, you're all set!
5. If not, see the troubleshooting section or consider switching to Ollama

See `ALTERNATIVE_SOLUTION.md` for instructions on switching to Ollama if needed.
