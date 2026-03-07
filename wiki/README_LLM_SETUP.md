# LLM Setup Guide - Choose Your Backend

You have **three options** for running the AI coach. Here's a quick comparison:

## Quick Comparison

| Option | Setup Time | Tool Calling | Reliability | Best For |
|--------|------------|--------------|-------------|----------|
| **Ollama Docker** ⭐ | 5 min | Excellent | Excellent | Production, reliability |
| LM Studio | 10 min | Good | Good | Visual management, UI |
| Ollama Local | 3 min | Excellent | Excellent | Development, testing |

## Recommended: Ollama in Docker ⭐

**Why this is the best option:**
- ✅ Reliable tool calling with LangChain ReAct agent
- ✅ Easy to set up and manage
- ✅ Runs in the background
- ✅ Consistent across environments
- ✅ No UI needed
- ✅ Works with models that don't have native tool calling

### Quick Start

```bash
# 1. Run the setup script
.\setup-ollama.ps1

# 2. Start your FastAPI server
uvicorn app.main:app --reload

# 3. Test at http://localhost:8000/chat.html
```

**That's it!** See `OLLAMA_DOCKER_SETUP.md` for details.

---

## Option 2: LM Studio (Current Setup)

**Good for:** Visual model management, trying different models easily

### Status
- ✅ Already configured
- ✅ Custom service created (`lmstudio_chat_service.py`)
- ⚠️ Uses heuristic-based goal extraction (not native tool calling)

### Quick Start

1. Make sure LM Studio is running with a model loaded
2. Update `.env`:
   ```env
   LLM_TYPE=lm-studio
   OLLAMA_ENDPOINT=http://localhost:1234
   OLLAMA_MODEL=openai/gpt-oss-20b
   ```
3. Restart FastAPI server

See `LM_STUDIO_NATIVE_API.md` for details.

---

## Option 3: Ollama Local (No Docker)

**Good for:** Quick testing, development

### Quick Start

```bash
# 1. Install Ollama from https://ollama.ai/

# 2. Pull a model
ollama pull mistral

# 3. Update .env
# LLM_TYPE=ollama
# OLLAMA_ENDPOINT=http://localhost:11434
# OLLAMA_MODEL=mistral

# 4. Restart FastAPI server
uvicorn app.main:app --reload
```

See `ALTERNATIVE_SOLUTION.md` for details.

---

## Files Created

### Setup Files
- `docker-compose.yml` - Ollama Docker configuration
- `setup-ollama.ps1` - Automated setup script

### Service Files
- `app/services/langchain_chat_service.py` - For Ollama (LangChain)
- `app/services/lmstudio_chat_service.py` - For LM Studio (native API)

### Documentation
- `OLLAMA_DOCKER_SETUP.md` - Ollama Docker guide (recommended)
- `LM_STUDIO_NATIVE_API.md` - LM Studio native API guide
- `LANGCHAIN_TOOL_CALLING_GUIDE.md` - LangChain tool calling details
- `ALTERNATIVE_SOLUTION.md` - All options comparison
- `QUICK_FIX_404.md` - Troubleshooting LM Studio 404 errors

---

## Current Configuration

Your `.env` is set to use **Ollama** (recommended):
```env
LLM_TYPE=ollama
OLLAMA_ENDPOINT=http://localhost:11434
OLLAMA_MODEL=mistral
```

To switch to LM Studio, change `LLM_TYPE=lm-studio` and update the endpoint.

---

## Testing Your Setup

### 1. Start the Backend

**For Ollama Docker:**
```bash
docker-compose up -d
```

**For LM Studio:**
- Open LM Studio
- Go to "Local Server" tab
- Start the server

### 2. Start FastAPI

```bash
uvicorn app.main:app --reload
```

### 3. Check the Logs

**For Ollama:**
```
[Chat API] Using LangChain-based chat service with agentic tool calling
[LangChain] Initializing with Ollama backend
```

**For LM Studio:**
```
[Chat API] Using LM Studio native chat service
[LMStudio] Endpoint: http://localhost:1234/api/v1/chat
```

### 4. Test the Chat

1. Go to http://localhost:8000/chat.html
2. Send this message:
   ```
   I want to lose weight for the bike Posidonia Tour. It is a route of 70km with 600m elevation gain. Now I am at 90.5kg. I want to be 85kg until May 30 that is the race day. I will participate in the amateur group.
   ```
3. Watch for goal confirmation in the response

### 5. Verify Goal Saved

- Go to http://localhost:8000/settings.html
- Check the "Goals" section
- Your goal should appear there

---

## Troubleshooting

### Ollama Issues
See `OLLAMA_DOCKER_SETUP.md` → Troubleshooting section

### LM Studio Issues
See `LM_STUDIO_NATIVE_API.md` → Troubleshooting section

### General Issues
See `LANGCHAIN_TOOL_CALLING_GUIDE.md` → Troubleshooting section

---

## Recommendation

**Start with Ollama Docker** (Option 1):
1. Run `.\setup-ollama.ps1`
2. Wait for model download
3. Start FastAPI server
4. Test the chat

It's the most reliable option and will give you the best experience with tool calling.

If you prefer a visual interface, stick with LM Studio (Option 2), but be aware that goal extraction is heuristic-based rather than using native tool calling.

---

## Need Help?

1. Check the relevant documentation file for your chosen option
2. Look at the troubleshooting sections
3. Check server logs for detailed error messages
4. Try the alternative option if one isn't working

Good luck! 🚀
