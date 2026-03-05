Bug 1 - Strava OAuth UI Flow:

Add "Connect Strava" button to index.html
Implement proper redirect handling in the callback endpoint
Display connection status with athlete information
Bug 2 - LLM Docker Endpoint:

Fix URL construction in llm_client.py to normalize base URL and use correct /v1/chat/completions path
Update Docker environment configuration
Ensure compatibility with both LM Studio (local) and Ollama (Docker)