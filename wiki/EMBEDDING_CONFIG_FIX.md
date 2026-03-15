# Embedding Configuration Fix

## Problem
The RAG engine was hardcoded to use Ollama endpoint (`http://localhost:11434`) for embeddings, even when the user was running LM Studio for the LLM. This caused connection errors when trying to generate embeddings.

## Solution
Made the embedding configuration flexible and independent from the LLM configuration:

### 1. Updated `app/config.py`
Added new configuration settings:
- `EMBEDDING_TYPE`: Choose between "ollama" or "lm-studio" (defaults to `LLM_TYPE`)
- `EMBEDDING_ENDPOINT`: Embedding service endpoint (defaults to appropriate endpoint based on type)
- `EMBEDDING_MODEL`: Embedding model name (default: "nomic-embed-text")

Added properties:
- `embedding_type`: Returns the embedding backend type
- `embedding_endpoint`: Returns the embedding endpoint URL with smart defaults

### 2. Updated `app/services/rag_engine.py`
- Removed hardcoded Ollama endpoint and model name
- Added support for both Ollama-style API (`/api/embeddings`) and OpenAI-style API (`/v1/embeddings`)
- `generate_embedding()` now detects the embedding type and uses the appropriate API format:
  - **Ollama**: `POST /api/embeddings` with `{"model": "...", "prompt": "..."}`
  - **LM Studio**: `POST /v1/embeddings` with `{"model": "...", "input": "..."}`
- Updated error messages to be more generic (not Ollama-specific)

### 3. Updated `.env`
Added commented-out embedding configuration examples:
```env
# Embedding Configuration
# Options: "ollama" or "lm-studio" (defaults to LLM_TYPE if not specified)
# EMBEDDING_TYPE=lm-studio
# EMBEDDING_ENDPOINT=http://localhost:1234
# EMBEDDING_MODEL=nomic-embed-text
```

## Usage

### Default Behavior (No Embedding Config)
If you don't set any embedding variables, the system will:
- Use the same backend as your LLM (`LLM_TYPE`)
- Use the appropriate endpoint automatically
- Use "nomic-embed-text" as the model

### Using LM Studio for Embeddings
To explicitly use LM Studio for embeddings, uncomment and set in `.env`:
```env
EMBEDDING_TYPE=lm-studio
EMBEDDING_ENDPOINT=http://localhost:1234
EMBEDDING_MODEL=nomic-embed-text
```

### Using Ollama for Embeddings (with LM Studio for LLM)
You can mix and match - use LM Studio for chat but Ollama for embeddings:
```env
LLM_TYPE=lm-studio
LM_STUDIO_MODEL=mistralai/ministral-3-14b-reasoning

EMBEDDING_TYPE=ollama
EMBEDDING_ENDPOINT=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
```

## Testing
After making these changes:
1. Restart the FastAPI server for changes to take effect
2. Check the startup logs to verify the embedding configuration:
   ```
   [RAGEngine] Initializing with embedding type: lm-studio
   [RAGEngine] Embedding endpoint: http://localhost:1234
   [RAGEngine] Using embedding model: nomic-embed-text
   ```
3. Send a chat message and verify embeddings are generated without errors

## Graceful Degradation
If the embedding service is not available:
- The system will log a warning but continue
- Chat will still work using only the active session buffer (Layer 1)
- Cross-session memory (Layer 2) will be unavailable until embeddings are working
