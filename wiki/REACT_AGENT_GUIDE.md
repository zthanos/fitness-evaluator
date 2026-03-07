# ReAct Agent for Improved Tool Calling

## What Changed

I've upgraded the LangChain service to use a **ReAct (Reasoning + Acting) agent** instead of simple tool binding. This significantly improves tool calling reliability, especially for models that need more guidance.

## What is ReAct?

ReAct is an agent framework that makes LLMs:
1. **Think** about what they need to do (Reasoning)
2. **Act** by calling tools (Acting)
3. **Observe** the results
4. **Repeat** until the task is complete

This structured approach helps models that struggle with direct tool calling.

## How It Works

### Traditional Approach (What We Had Before):
```
User: "I want to lose weight from 90.5kg to 85kg by May 30"
LLM: "That's a great goal! [mentions saving but doesn't call tool]"
❌ Tool not called
```

### ReAct Agent Approach (What We Have Now):
```
User: "I want to lose weight from 90.5kg to 85kg by May 30"

Agent Thought: "I need to save this goal. Let me use the save_athlete_goal tool."
Agent Action: save_athlete_goal
Agent Action Input: {"goal_type": "weight_loss", "target_value": 85, ...}
Agent Observation: "✅ Goal saved! ID: abc-123"
Agent Thought: "Goal saved successfully. Now I can respond to the user."
Agent Final Answer: "✅ Goal saved! I've set up your weight loss goal..."

✅ Tool called successfully!
```

## Benefits

1. **More Reliable**: Explicitly guides the model through the reasoning process
2. **Better for Weaker Models**: Works with models that don't have native tool calling
3. **Transparent**: You can see the agent's reasoning in the logs
4. **Self-Correcting**: Can retry if something goes wrong

## Configuration

No configuration needed! The ReAct agent is automatically used when you have:
```env
LLM_TYPE=ollama
```

## Testing

1. **Start Ollama** (if using Docker):
   ```bash
   docker-compose up -d
   ```

2. **Make sure your model is pulled**:
   ```bash
   docker exec -it fitness-ollama ollama list
   ```

3. **Restart FastAPI server**:
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Check the logs** - you should see:
   ```
   [LangChain] Using ReAct agent for improved tool calling
   ```

5. **Test the chat** with your goal message

6. **Watch the agent work** in the logs:
   ```
   [LangChain] Invoking ReAct agent
   [LangChain] Tool called: save_athlete_goal
   [LangChain] Tool result: ✅ Goal saved! ID: ...
   [LangChain] ✅ Agent successfully called 1 tool(s)
   ```

## Recommended Models for ReAct

### Best Performance:
1. **mistral** (4GB) - Good balance, works well with ReAct
2. **llama2:13b** (7GB) - Excellent reasoning, very reliable
3. **mixtral** (26GB) - Best quality, requires lots of RAM

### For Testing:
1. **mistral** (4GB) - Fast and capable
2. **gpt-oss:20b** (11GB) - Good quality, should work better with ReAct

### Not Recommended:
- Very small models (< 3GB) - May struggle with the ReAct format
- Models not trained on instruction following

## Troubleshooting

### Agent Still Not Calling Tools

**Check the logs** for the agent's reasoning:
```
Agent Thought: ...
Agent Action: ...
```

If you see the agent thinking but not acting, try:

1. **Use a larger model**:
   ```bash
   docker exec -it fitness-ollama ollama pull llama2:13b
   ```
   
   Update `.env`:
   ```env
   OLLAMA_MODEL=llama2:13b
   ```

2. **Make your goal message more explicit**:
   ```
   Please save this goal: I want to lose weight from 90.5kg to 85kg by May 30 for the Posidonia Tour race.
   ```

3. **Check if the model is loaded**:
   ```bash
   docker exec -it fitness-ollama ollama list
   ```

### Agent Takes Too Long

The ReAct agent can take a bit longer because it reasons through the problem. This is normal.

**To speed it up:**
- Use a smaller model (mistral instead of llama2:13b)
- Reduce `max_iterations` in the code (currently set to 5)

### Agent Errors Out

**Check the logs** for parsing errors. The agent might be having trouble with the ReAct format.

**Solutions:**
1. Try a different model (mistral is most reliable)
2. Simplify your message
3. Restart the FastAPI server

## Comparison: Direct Tool Calling vs ReAct Agent

| Feature | Direct Tool Calling | ReAct Agent |
|---------|---------------------|-------------|
| Speed | Faster | Slightly slower |
| Reliability | Model-dependent | More reliable |
| Transparency | Limited | Full reasoning visible |
| Model Requirements | Needs native support | Works with most models |
| Best For | GPT-4, Claude | Ollama models, weaker LLMs |

## Advanced: Customizing the ReAct Prompt

The ReAct prompt is in `app/services/langchain_chat_service.py` in the `_create_react_agent()` method.

You can customize:
- The system prompt
- The reasoning format
- The number of iterations (`max_iterations`)
- Error handling behavior

## Next Steps

1. Test with your current model (`gpt-oss:20b`)
2. If it works, you're all set!
3. If not, try `mistral` or `llama2:13b`
4. Watch the logs to see the agent's reasoning process

The ReAct agent should significantly improve tool calling reliability! 🎉
