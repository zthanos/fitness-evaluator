# app/services/llm_client.py
import httpx
import asyncio
import json
from app.config import get_settings

SYSTEM_PROMPT_PATH = "app/prompts/system_prompt.txt"


async def generate_evaluation(contract: dict) -> str:
    """
    Send the contract to LM Studio or Ollama and return the raw JSON string response.
    Retries up to 3 times with exponential backoff on connection errors.
    Raises ValueError if the response is not valid JSON.
    """
    settings = get_settings()
    
    # Read system prompt from file
    try:
        with open(SYSTEM_PROMPT_PATH, 'r') as f:
            system_prompt = f.read()
    except FileNotFoundError:
        raise ValueError(f"System prompt file not found at {SYSTEM_PROMPT_PATH}")
    
    user_message = json.dumps(contract, indent=2, default=str)

    payload = {
        "model": settings.LM_STUDIO_MODEL,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    }
    
    # Construct endpoint URL based on LLM type
    if settings.is_ollama:
        endpoint_url = f"{settings.llm_base_url}/chat/completions"
    else:
        # LM Studio uses /v1 prefix
        endpoint_url = f"{settings.llm_base_url}/chat/completions"

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload
                )
                response.raise_for_status()
                raw = response.json()["choices"][0]["message"]["content"]
                json.loads(raw)  # validate it's parseable
                return raw
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")

