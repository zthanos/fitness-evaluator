from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "sqlite:///./fitness_eval.db"

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
    
    # Web Search Configuration
    TAVILY_API_KEY: str = ""  # Get free API key at https://tavily.com
    
    # Backward compatibility with old env var name
    LM_STUDIO_BASE_URL: str = ""  # Deprecated, use LM_STUDIO_ENDPOINT
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    API_WORKERS: int = 1
    
    # Environment
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    
    # Derived settings (read-only after init)
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    
    @property
    def llm_base_url(self) -> str:
        """Get the LLM endpoint URL, handling backward compatibility."""
        # Prefer explicit Ollama endpoint when using Ollama
        if self.is_ollama and self.OLLAMA_ENDPOINT:
            return self.OLLAMA_ENDPOINT
        if self.LM_STUDIO_BASE_URL:
            return self.LM_STUDIO_BASE_URL
        return self.LM_STUDIO_ENDPOINT
    
    @property
    def is_ollama(self) -> bool:
        """Check if using Ollama as LLM backend."""
        return self.LLM_TYPE.lower() == "ollama"
    
    @property
    def is_lm_studio(self) -> bool:
        """Check if using LM Studio as LLM backend."""
        return self.LLM_TYPE.lower() == "lm-studio"

@lru_cache
def get_settings() -> Settings:
    return Settings()
