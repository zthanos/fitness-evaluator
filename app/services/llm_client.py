# app/services/llm_client.py
import httpx
import asyncio
import json
from app.config import get_settings

def normalize_base_url(base_url: str) -> str:
    """
    Normalize the base URL by:
    1. Stripping trailing slashes (including multiple)
    2. Removing /api suffix if present

    Examples:
        "http://ollama:11434/api" -> "http://ollama:11434"
        "http://ollama:11434/api/" -> "http://ollama:11434"
        "http://ollama:11434/api///" -> "http://ollama:11434"
        "http://localhost:1234" -> "http://localhost:1234"
        "http://localhost:1234/" -> "http://localhost:1234"
    """
    # Strip all trailing slashes
    normalized = base_url.rstrip('/')

    # Remove /api suffix if present
    if normalized.endswith('/api'):
        normalized = normalized[:-4]  # Remove the last 4 characters ("/api")

    return normalized


def construct_openai_endpoint(base_url: str) -> str:
    """
    Construct the OpenAI-compatible endpoint URL.

    Takes a base URL (potentially with /api suffix or trailing slashes)
    and returns the correct OpenAI-compatible endpoint with /v1/chat/completions.

    Args:
        base_url: The base URL (e.g., "http://ollama:11434/api" or "http://localhost:1234")

    Returns:
        The full OpenAI-compatible endpoint URL (e.g., "http://ollama:11434/v1/chat/completions")

    Examples:
        "http://ollama:11434/api" -> "http://ollama:11434/v1/chat/completions"
        "http://ollama:11434/api/" -> "http://ollama:11434/v1/chat/completions"
        "http://localhost:1234" -> "http://localhost:1234/v1/chat/completions"
    """
    normalized = normalize_base_url(base_url)
    return f"{normalized}/v1/chat/completions"

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

    # Choose model based on backend
    model_name = settings.OLLAMA_MODEL if settings.is_ollama else settings.LM_STUDIO_MODEL

    payload = {
        "model": model_name,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    }
    
    # Construct endpoint URL using normalization to handle /api suffix and trailing slashes
    endpoint_url = construct_openai_endpoint(settings.llm_base_url)

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

