"""
app/core/config.py
------------------
Single source of truth for all application configuration.

Uses pydantic-settings to:
  - Load values from the `.env` file automatically.
  - Validate types and raise clear errors for missing variables at startup.
  - Expose a typed `Settings` singleton used everywhere in the app.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.

    All fields map 1-to-1 to the keys defined in `.env.example`.
    pydantic-settings will raise a `ValidationError` at startup if any
    required field is missing, giving a clear developer error message.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",            # Silently ignore unknown env vars
    )

    # ------------------------------------------------------------------
    # Google AI credentials
    # ------------------------------------------------------------------
    GEMINI_API_KEY: str

    # ------------------------------------------------------------------
    # System prompts — loaded from .env, never hardcoded in Python logic
    # ------------------------------------------------------------------
    PROMPT_GENERATE_CODE: str
    PROMPT_EXPLAIN_CODE: str
    PROMPT_ANALYZE_COMPLEXITY: str
    PROMPT_RUBBER_DUCK: str
    PROMPT_CONVERT_LANGUAGE: str
    PROMPT_GENERATE_DOCSTRING: str

    # ------------------------------------------------------------------
    # Optional tunables (sensible defaults keep .env minimal)
    # ------------------------------------------------------------------
    GEMINI_MODEL: str = "gemini-2.5-flash"
    APP_TITLE: str = "AI Coding Assistant API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Using `lru_cache` means the .env file is read exactly once per
    process, making this safe and efficient to call from anywhere.
    """
    return Settings()
