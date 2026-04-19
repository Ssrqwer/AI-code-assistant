"""
app/core/config.py
------------------
Single source of truth for all application configuration.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Google AI credentials - NOW SUPPORTS MULTIPLE KEYS
    # ------------------------------------------------------------------
    GEMINI_API_KEYS: str  # Comma-separated: "key1,key2,key3"
    
    @property
    def GEMINI_API_KEYS_LIST(self) -> List[str]:
        """Parse comma-separated keys into a list, stripping whitespace."""
        return [k.strip() for k in self.GEMINI_API_KEYS.split(",") if k.strip()]

    # Backward compatibility - first key as default
    @property
    def GEMINI_API_KEY(self) -> str:
        """Return first key for backward compatibility."""
        keys = self.GEMINI_API_KEYS_LIST
        if not keys:
            raise ValueError("No GEMINI_API_KEYS provided")
        return keys[0]

    # ------------------------------------------------------------------
    # System prompts
    # ------------------------------------------------------------------
    PROMPT_GENERATE_CODE: str
    PROMPT_EXPLAIN_CODE: str
    PROMPT_ANALYZE_COMPLEXITY: str
    PROMPT_RUBBER_DUCK: str
    PROMPT_CONVERT_LANGUAGE: str
    PROMPT_GENERATE_DOCSTRING: str

    # ------------------------------------------------------------------
    # Optional tunables
    # ------------------------------------------------------------------
    GEMINI_MODEL: str = "gemini-2.5-flash"
    APP_TITLE: str = "AI Coding Assistant API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()