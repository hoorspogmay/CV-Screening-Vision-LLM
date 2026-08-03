"""
Application configuration.

All environment-driven settings live here. To switch AI providers, change
AI_PROVIDER (and the matching API key) in the .env file only — no other
code needs to change.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- AI provider selection -------------------------------------------------
    # Supported values: "groq", "openrouter", "auto", or other future providers.
    ai_provider: str = "groq"

    # --- Groq ---------------------------------------------------------------
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_api_url: str = "https://api.groq.com/openai/v1/chat/completions"

    # --- OpenRouter --------------------------------------------------------
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen-2.5-7b-instruct"
    openrouter_api_url: str = "https://openrouter.ai/api/v1/chat/completions"

    # --- Google / Gemini ---------------------------------------------------
    google_api_key: str = ""
    google_model: str = "google/gemma-4-31b-it:free"
    google_api_url: str = ""

    # --- Claude ------------------------------------------------------------
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-latest"
    claude_api_url: str = "https://api.anthropic.com/v1/messages"

    # --- Generic provider knobs (used by whichever provider is active) ------
    ai_request_timeout_seconds: int = 25
    ai_max_retries: int = 2
    ai_retry_backoff_seconds: float = 0.8
    ai_rate_limit_pause_seconds: float = 1.0

    # --- Concurrency ----------------------------------------------------------
    # Max resumes evaluated against the AI provider at the same time.
    max_concurrent_evaluations: int = 3

    # --- Hiring policy defaults ----------------------------------------------
    allow_overqualified: bool = False
    allow_internships: bool = False

    # --- Uploads --------------------------------------------------------------
    max_upload_size_mb: int = 15
    allowed_extensions: tuple = (".pdf", ".docx")

    # --- CORS -------------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Settings are cached so the .env file is only parsed once per process."""
    return Settings()
