from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database (PostgreSQL via docker-compose)
    DATABASE_URL: str = "postgresql://fitness_user:fitness_password@localhost:5460/fitness"

    # Keycloak / OIDC
    KEYCLOAK_URL: str = "http://localhost:8081"
    KEYCLOAK_REALM: str = "fitness"
    KEYCLOAK_CLIENT_ID: str = "fitness-app"

    # Strava OAuth
    STRAVA_CLIENT_ID: str = ""
    STRAVA_CLIENT_SECRET: str = ""
    STRAVA_REDIRECT_URI: str = "http://localhost:8000/api/auth/strava/callback"
    STRAVA_ENCRYPTION_KEY: str = ""

    # LLM Configuration - supports both LM Studio and Ollama
    LLM_TYPE: Literal["lm-studio", "ollama"] = "ollama"
    LM_STUDIO_ENDPOINT: str = "http://localhost:1234"
    LM_STUDIO_MODEL: str = "mistral"

    # Ollama-specific configuration (OpenAI-compatible endpoint)
    OLLAMA_ENDPOINT: str = ""
    OLLAMA_MODEL: str = "mistral"

    # Tool-calling subagent — a separate model used only for the ReAct tool loop.
    # Should be a model with reliable function-calling support (e.g. Llama 3.1 8B).
    # If empty, falls back to the primary LLM (LM_STUDIO_MODEL / OLLAMA_MODEL).
    TOOL_AGENT_MODEL: str = ""
    TOOL_AGENT_ENDPOINT: str = ""  # defaults to LM_STUDIO_ENDPOINT / OLLAMA_ENDPOINT

    # Embedding Configuration
    # Options: "ollama" or "lm-studio" (defaults to same as LLM_TYPE)
    EMBEDDING_TYPE: str = ""  # If empty, uses LLM_TYPE
    EMBEDDING_ENDPOINT: str = ""  # If empty, uses OLLAMA_ENDPOINT or LM_STUDIO_ENDPOINT
    EMBEDDING_MODEL: str = "nomic-embed-text"  # Default embedding model
    EMBEDDING_TIMEOUT: int = 10  # Seconds before giving up on embedding service

    # Web Search Configuration
    TAVILY_API_KEY: str = ""  # Get free API key at https://tavily.com

    # Backward compatibility with old env var name
    LM_STUDIO_BASE_URL: str = ""  # Deprecated, use LM_STUDIO_ENDPOINT

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    API_WORKERS: int = 1

    # Chat Runtime Feature Flags (Phase 6)
    #
    # Routing precedence (evaluated in ChatMessageHandler):
    #   1. USE_CE_CHAT_RUNTIME=True  → all users use CE runtime (global override)
    #   2. PILOT_ROLLOUT_ENABLED=True → users in PILOT_USER_IDS use CE, rest use legacy
    #   3. Both False                → all users use legacy runtime
    #
    # ENABLE_RUNTIME_COMPARISON runs both paths in parallel for non-production QA only.
    USE_CE_CHAT_RUNTIME: bool = False  # Toggle CE chat runtime globally (default: legacy)
    LEGACY_CHAT_ENABLED: bool = True   # Keep legacy path available for rollback
    CE_CHAT_TOKEN_BUDGET: int = 2400   # Token budget for CE context builder
    CE_CHAT_MAX_TOOL_ITERATIONS: int = 5  # Max tool orchestration iterations
    ENABLE_RUNTIME_COMPARISON: bool = False  # Side-by-side comparison mode (non-production only)

    # Pilot Rollout (Phase 6.6)
    PILOT_USER_IDS: str = ""  # Comma-separated user IDs for pilot CE runtime rollout
    PILOT_ROLLOUT_ENABLED: bool = False  # Master switch for pilot-based routing

    # Environment
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"

    # Derived settings (read-only after init)
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    @property
    def keycloak_issuer(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"

    @property
    def keycloak_jwks_uri(self) -> str:
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"

    @property
    def llm_base_url(self) -> str:
        if self.LLM_TYPE.lower() == "lm-studio":
            return self.LM_STUDIO_ENDPOINT or self.LM_STUDIO_BASE_URL or "http://localhost:1234"
        return self.OLLAMA_ENDPOINT if self.OLLAMA_ENDPOINT else "http://localhost:11434"

    @property
    def is_ollama(self) -> bool:
        return self.LLM_TYPE.lower() == "ollama"

    @property
    def tool_agent_base_url(self) -> str:
        """Endpoint for the tool-calling subagent (falls back to primary endpoint)."""
        return self.TOOL_AGENT_ENDPOINT or self.llm_base_url

    @property
    def tool_agent_model(self) -> str:
        """Model name for the tool-calling subagent (falls back to primary model)."""
        if self.TOOL_AGENT_MODEL:
            return self.TOOL_AGENT_MODEL
        return self.LM_STUDIO_MODEL if not self.is_ollama else self.OLLAMA_MODEL

    @property
    def pilot_user_ids_set(self) -> set:
        """Parse PILOT_USER_IDS into a set of integers."""
        if not self.PILOT_USER_IDS:
            return set()
        try:
            return {int(uid.strip()) for uid in self.PILOT_USER_IDS.split(",") if uid.strip()}
        except ValueError:
            return set()

    @property
    def embedding_type(self) -> str:
        """Get the embedding backend type (defaults to LLM_TYPE if not specified)."""
        return self.EMBEDDING_TYPE.lower() if self.EMBEDDING_TYPE else self.LLM_TYPE.lower()

    @property
    def embedding_endpoint(self) -> str:
        """Get the embedding endpoint URL."""
        if self.EMBEDDING_ENDPOINT:
            return self.EMBEDDING_ENDPOINT
        # Default to appropriate endpoint based on embedding type
        return self.OLLAMA_ENDPOINT if self.OLLAMA_ENDPOINT else "http://localhost:11434"


@lru_cache
def get_settings() -> Settings:
    return Settings()
