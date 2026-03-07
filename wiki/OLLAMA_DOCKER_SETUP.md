# Ollama Docker Setup - Recommended Solution

Using Ollama in Docker is the best solution because:
- ✅ Reliable tool calling with LangChain
- ✅ Easy to set up and manage
- ✅ Isolated from your system
- ✅ Works consistently across environments
- ✅ No UI needed - just works

## Quick Setup

### 1. Start Ollama in Docker

```bash
# Start Ollama container
docker-compose up -d

# Check if it's running
docker ps
```

You should see:
```
CONTAINER ID   IMAGE                  STATUS         PORTS
xxxxx          ollama/ollama:latest   Up 2 seconds   0.0.0.0:11434->11434/tcp
```

### 2. Pull a Model

```bash
# Pull Mistral (good balance of speed and capability)
docker exec -it fitness-ollama ollama pull mistral

# OR pull Llama 2 13B (better tool calling, but slower and larger)
# docker exec -it fitness-ollama ollama pull llama2:13b

# OR pull Mistral OpenOrca (optimized for instructions)
# docker exec -it fitness-ollama ollama pull mistral-openorca
```

Wait for the download to complete (Mistral is ~4GB).

### 3. Verify the Model

```bash
# List available models
docker exec -it fitness-ollama ollama list
```

You should see:
```
NAME              ID              SIZE      MODIFIED
mistral:latest    xxxxx           4.1 GB    X seconds ago
```

### 4. Update Your `.env`

```env
LLM_TYPE=ollama
OLLAMA_ENDPOINT=http://localhost:11434
OLLAMA_MODEL=mistral
```

### 5. Restart Your FastAPI Server

```bash
uvicorn app.main:app --reload
```

You should see in the logs:
```
[Chat API] Using LangChain-based chat service with agentic tool calling
[LangChain] Initializing with Ollama backend
[LangChain] Backend: ollama, Endpoint: http://localhost:11434, Model: mistral
```

### 6. Test It!

1. Go to http://localhost:8000/chat.html
2. Send your goal message:
   ```
   I want to lose weight for the bike Posidonia Tour. It is a route of 70km with 600m elevation gain. Now I am at 90.5kg. I want to be 85kg until May 30 that is the race day. I will participate in the amateur group.
   ```
3. Watch the server logs for:
   ```
   [LangChain] Tool calls detected: 1
   [LangChain] Executing tool: save_athlete_goal
   [LangChain] Tool result: ✅ Goal saved! ID: ...
   ```

## Managing Ollama

### Stop Ollama
```bash
docker-compose down
```

### Start Ollama
```bash
docker-compose up -d
```

### View Ollama Logs
```bash
docker logs fitness-ollama
```

### Pull Additional Models
```bash
# List available models on Ollama
docker exec -it fitness-ollama ollama list

# Pull a new model
docker exec -it fitness-ollama ollama pull <model-name>

# Remove a model
docker exec -it fitness-ollama ollama rm <model-name>
```

### Test Ollama Directly
```bash
# Test with a simple prompt
docker exec -it fitness-ollama ollama run mistral "Hello, how are you?"
```

## Recommended Models

### For Best Tool Calling:
1. **mistral** (4GB) - Good balance, reliable tool calling
2. **llama2:13b** (7GB) - Better reasoning, more reliable tools
3. **mistral-openorca** (4GB) - Optimized for following instructions

### For Speed:
1. **mistral** (4GB) - Fast and capable
2. **phi** (1.6GB) - Very fast, but less capable

### For Quality:
1. **llama2:13b** (7GB) - Best quality, slower
2. **mixtral** (26GB) - Excellent quality, requires lots of RAM

## Troubleshooting

### Container Won't Start

**Check if port 11434 is already in use:**
```bash
# Windows PowerShell
netstat -ano | findstr :11434
```

**Solution**: Stop any other Ollama instance or change the port in `docker-compose.yml`

### Model Download Fails

**Check your internet connection and try again:**
```bash
docker exec -it fitness-ollama ollama pull mistral
```

### "Connection refused" Error

**Make sure the container is running:**
```bash
docker ps
```

**Restart the container:**
```bash
docker-compose restart
```

### Tool Calling Not Working

**Try a different model:**
```bash
# Llama 2 13B has better tool calling
docker exec -it fitness-ollama ollama pull llama2:13b
```

Update `.env`:
```env
OLLAMA_MODEL=llama2:13b
```

Restart FastAPI server.

## Advantages Over LM Studio

| Feature | Ollama Docker | LM Studio |
|---------|---------------|-----------|
| Setup | Very Easy | Medium |
| Tool Calling | Native (excellent) | Heuristic (good) |
| Management | CLI | GUI |
| Resource Usage | Efficient | Efficient |
| Reliability | Excellent | Good |
| Cross-platform | Yes | Yes |
| Background Service | Yes | Requires app open |

## Performance Tips

### 1. Use GPU (if available)

Uncomment the GPU section in `docker-compose.yml`:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

Requires: nvidia-docker installed

### 2. Adjust Model Size

- **Low RAM (8GB)**: Use `mistral` or `phi`
- **Medium RAM (16GB)**: Use `mistral` or `llama2:7b`
- **High RAM (32GB+)**: Use `llama2:13b` or `mixtral`

### 3. Keep Container Running

The `docker-compose.yml` is configured with `restart: unless-stopped`, so Ollama will automatically start when your system boots.

## Next Steps

1. Start Ollama: `docker-compose up -d`
2. Pull a model: `docker exec -it fitness-ollama ollama pull mistral`
3. Update `.env` to use Ollama
4. Restart FastAPI server
5. Test the chat with your goal message
6. Enjoy reliable tool calling! 🎉

## Switching Back to LM Studio

If you want to switch back to LM Studio later:

1. Update `.env`:
   ```env
   LLM_TYPE=lm-studio
   OLLAMA_ENDPOINT=http://localhost:1234
   OLLAMA_MODEL=openai/gpt-oss-20b
   ```

2. Restart FastAPI server

3. The LM Studio native service will be used automatically

## Need Help?

- Ollama Documentation: https://ollama.ai/
- Available Models: https://ollama.ai/library
- Docker Documentation: https://docs.docker.com/

The Ollama Docker setup is the recommended approach for production use!
